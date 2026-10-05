//! Bounded local IPC to the reference SV2 cryptography. No socket or wallet access.
use noise_sv2::{Initiator, NoiseEngine, INITIATOR_EXPECTED_HANDSHAKE_MESSAGE_SIZE};
use serde_json::{json, Value};
use std::io::{self, BufRead, Read, Write};

fn bytes(value: &Value) -> Result<Vec<u8>, String> {
    let text=value.as_str().ok_or("expected hex")?;
    if text.len()>131072 || text.len()%2!=0 || !text.is_ascii() { return Err("bounded ASCII even hex required".into()); }
    (0..text.len()).step_by(2).map(|i|u8::from_str_radix(&text[i..i+2],16).map_err(|_|"invalid hex".into())).collect()
}
fn hex(data: &[u8]) -> String { data.iter().map(|b|format!("{b:02x}")).collect() }
fn main() {
    let mut initiator:Option<Box<Initiator>>=None;
    let mut codec:Option<NoiseEngine>=None;
    #[cfg(feature="fixtures")]
    let mut responder:Option<Box<noise_sv2::Responder>>=None;
    let mut input=io::stdin().lock();
    loop {
        let mut line=Vec::new();
        let count=Read::by_ref(&mut input).take(140001).read_until(b'\n',&mut line);
        if matches!(count,Ok(0)){break;}
        let result=(|| -> Result<Value,String> {
            count.map_err(|_|"IPC read failed")?;
            if line.len()>140000 {return Err("IPC bound exceeded".into());}
            let request:Value=serde_json::from_slice(&line).map_err(|_|"invalid request")?;
            let data=bytes(&request["data"])?;
            match request["op"].as_str().ok_or("missing operation")? {
                #[cfg(feature="fixtures")]
                "fixture-init" => {
                    use secp256k1::{Keypair,Secp256k1,SecretKey};
                    let private=[1u8;32];let secret=SecretKey::from_slice(&private).map_err(|_|"fixture secret")?;
                    let public=Keypair::from_secret_key(&Secp256k1::new(),&secret).x_only_public_key().0.serialize();
                    responder=Some(noise_sv2::Responder::from_authority_kp(&public,&private,std::time::Duration::from_secs(60)).map_err(|_|"fixture responder")?);
                    Ok(json!({"data":hex(&public)}))
                }
                #[cfg(feature="fixtures")]
                "fixture-handshake" => {
                    let first:[u8;64]=data.try_into().map_err(|_|"fixture handshake length")?;
                    let (reply,state)=responder.as_mut().ok_or("fixture not initialized")?.step_1(first).map_err(|_|"fixture handshake")?;
                    codec=Some(state);responder=None;Ok(json!({"data":hex(&reply)}))
                }
                "init" => {
                    if initiator.is_some() || codec.is_some() {return Err("already initialized".into());}
                    let key:[u8;32]=data.try_into().map_err(|_|"authority key must be 32 bytes")?;
                    let mut state=Initiator::from_raw_k(key).map_err(|_|"invalid authority key")?;
                    let message=state.step_0().map_err(|_|"handshake initiation failed")?;
                    initiator=Some(state);Ok(json!({"data":hex(&message)}))
                }
                "finish" => {
                    let message:[u8;INITIATOR_EXPECTED_HANDSHAKE_MESSAGE_SIZE]=data.try_into().map_err(|_|"invalid handshake length")?;
                    let state=initiator.as_mut().ok_or("handshake not initialized")?;
                    codec=Some(state.step_2(message).map_err(|_|"server authentication failed")?);
                    initiator=None;Ok(json!({"data":""}))
                }
                "encrypt" | "decrypt" => {
                    let mut data=data;let state=codec.as_mut().ok_or("authenticated handshake required")?;
                    if request["op"]=="encrypt" {state.encrypt(&mut data).map_err(|_|"encryption failed")?;}
                    else {state.decrypt(&mut data).map_err(|_|"ciphertext authentication failed")?;}
                    Ok(json!({"data":hex(&data)}))
                }
                _=>Err("unknown operation".into())
            }
        })();
        match result {
            Ok(value)=>println!("{value}"),
            Err(error)=>{println!("{}",json!({"error":error})); let _=io::stdout().flush();break;}
        }
        if io::stdout().flush().is_err(){break;}
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use noise_sv2::Responder;
    use secp256k1::{Keypair,Secp256k1,SecretKey};
    use std::time::Duration;
    #[test]
    fn malformed_hex_is_bounded_and_does_not_panic() {
        assert!(bytes(&json!("é0")).is_err());assert!(bytes(&json!("0")).is_err());
        assert!(bytes(&json!("ff".repeat(65537))).is_err());assert_eq!(bytes(&json!("00ff")).unwrap(),vec![0,255]);
    }
    fn responder() -> ([u8;32],Box<Responder>) {
        // Synthetic fixture, never a wallet key or production authority.
        let private=[1u8;32];let secret=SecretKey::from_slice(&private).unwrap();
        let key=Keypair::from_secret_key(&Secp256k1::new(),&secret);
        let public=key.x_only_public_key().0.serialize();
        (public,Responder::from_authority_kp(&public,&private,Duration::from_secs(60)).unwrap())
    }
    #[test]
    fn authenticated_roundtrip_and_tamper() {
        let (public,mut server)=responder();let mut client=Initiator::from_raw_k(public).unwrap();
        let first=client.step_0().unwrap();let (reply,mut receiving)=server.step_1(first).unwrap();
        let mut sending=client.step_2(reply).unwrap();
        let mut message=b"exact Bitcoin transport".to_vec();sending.encrypt(&mut message).unwrap();
        receiving.decrypt(&mut message).unwrap();assert_eq!(message,b"exact Bitcoin transport");
        let mut corrupted=b"tamper test".to_vec();sending.encrypt(&mut corrupted).unwrap();corrupted[0]^=1;
        assert!(receiving.decrypt(&mut corrupted).is_err());
    }
    #[test]
    fn wrong_authority_is_rejected() {
        let (_,mut server)=responder();let private=SecretKey::from_slice(&[2u8;32]).unwrap();
        let public=Keypair::from_secret_key(&Secp256k1::new(),&private).x_only_public_key().0.serialize();
        let mut client=Initiator::from_raw_k(public).unwrap();
        let (reply,_)=server.step_1(client.step_0().unwrap()).unwrap();assert!(client.step_2(reply).is_err());
    }
}
