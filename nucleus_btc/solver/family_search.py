def amortized_value(surviving_candidates,saving_seconds_per_candidate,hunt_seconds):
    if surviving_candidates<0 or saving_seconds_per_candidate<0 or hunt_seconds<0:raise ValueError("Negative family cost")
    value=surviving_candidates*saving_seconds_per_candidate-hunt_seconds
    return {"net_seconds_saved":value,"economically_positive":value>0}
