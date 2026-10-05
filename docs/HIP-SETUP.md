# Optional Windows HIP and exact matrix probe

RX 7600 XT / gfx1102 appears in AMD's Windows HIP SDK support list. No SDK
compiler was detected in this workspace's Phase-II probe. OpenCL remains active.

Minimal manual setup: use the official Windows installer, select HIP SDK Core
and development headers/libraries, and retain the installed graphics driver
unless AMD explicitly requires an update. Set HIP_PATH to the installed SDK
directory for the current terminal. Verify `hipconfig` and `hipInfo` identify
gfx1102. Do not use factory reset or an unattended bundled driver installation.

Build the optional ordinary digest backend:

```powershell
cmake -S . -B build/hip -DNUCLEUS_ENABLE_HIP=ON -DCMAKE_HIP_ARCHITECTURES=gfx1102
cmake --build build/hip --config Release
```

Copying the resulting DLL into the normal build directory is optional; run
independent digest parity before selecting HIP. The current project provides
HIP digest hashing, not a production HIP scan implementation.

If the installed Windows CMake/generator does not support HIP language, use the
SDK compiler directly in an SDK/Visual Studio developer terminal instead:

```powershell
hipcc.bat --offload-arch=gfx1102 -std=c++20 -O3 -shared native/hip/baseline.hip -o build/nucleus_hip.dll
hipcc.bat --offload-arch=gfx1102 -std=c++20 -O3 -I C:/path/to/rocWMMA/library/include native/hip/family_matrix.hip -o build/nucleus-family-matrix.exe
```

Both routes are unverified in the present SDK-free environment. Record the
compiler/runtime versions and perform parity before any timing or backend switch.

The bounded matrix probe maps only Sigma1's exact GF(2) transform. Binary 0/1
inputs are represented exactly in half precision, dot products are at most 3,
and float accumulators contain exact integers. Parity is taken only afterward.
It includes host conversion, allocation, upload, kernel, download and packing.
It does not map modular SHA additions to matrix hardware.

With a matching rocWMMA header installation:

```powershell
cmake -S . -B build/hip-matrix -DNUCLEUS_ENABLE_HIP=ON -DNUCLEUS_ENABLE_WMMA=ON -DCMAKE_HIP_ARCHITECTURES=gfx1102 -DROCWMMA_INCLUDE_DIR=C:/path/to/rocWMMA/library/include
cmake --build build/hip-matrix --config Release
./build/hip-matrix/Release/nucleus-family-matrix.exe
```

This source is **uncompiled/unverified** until the optional toolchain exists.
The tested portable matrix proxy is slower; that result does not measure WMMA.

Sources consulted 5 October 2026:
[AMD Windows support](https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/shared/hipsdk/reference/system-requirements.html),
[installation](https://rocm.docs.amd.com/projects/install-on-windows/en/latest/install/install.html),
[rocWMMA architectures and data types](https://rocm.docs.amd.com/projects/rocWMMA/en/docs-7.0.2/api-reference/api-reference-guide.html).
