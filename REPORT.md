# Report

## Initial vLLM Configuration explanation

```shell
# Used as a starting point for K8s Pod
vllm serve Qwen/Qwen3-4B-Instruct-2507-FP8 --port 8000 --trust-remote-code --max-model-len 32768 --enable-chunked-prefill --max-num-batched-tokens 1024
```

- --trust-remote-code - Trusts custom python code shipped with the model
- --max-model-len 32768 - Caps the maximum context length, lowers GPU Mem usage
- --enable-chunked-prefill - Instead of processing on big promt in one go, vLLM splits it into multiple chunks, so long prompts don't block short generations from making progress.
- --max-num-batched-tokens 1024 -  Caps total number of tokens processed in a single scheduler iterations. With chunked prefill enabled, this is the main lever for balancing throughput vs. latency

---

## SLOs

### Iteration 0

On the first iteration the SLO wasn't hit. Not only it wasn't met - the agent began to crush after 20 seconds of 10 RPS. 
Sometimes it even manages to crush the whole cluster due to high CPU+GPU load on vLLM, LangFuse (+ its underlying workloads, such as clickhouse) and agent process.

```log
INFO:     127.0.0.1:38008 - "POST /answer HTTP/1.1" 200 OK
INFO:     127.0.0.1:38170 - "POST /answer HTTP/1.1" 200 OK
INFO:     127.0.0.1:38374 - "POST /answer HTTP/1.1" 200 OK
INFO:     127.0.0.1:38410 - "POST /answer HTTP/1.1" 200 OK
INFO:     127.0.0.1:60678 - "POST /answer HTTP/1.1" 200 OK
INFO:     127.0.0.1:60702 - "POST /answer HTTP/1.1" 200 OK
INFO:     127.0.0.1:38158 - "POST /answer HTTP/1.1" 200 OK
INFO:     127.0.0.1:37996 - "POST /answer HTTP/1.1" 200 OK
INFO:     127.0.0.1:60726 - "POST /answer HTTP/1.1" 200 OK
INFO:     127.0.0.1:38032 - "POST /answer HTTP/1.1" 200 OK
INFO:     127.0.0.1:60740 - "POST /answer HTTP/1.1" 200 OK
INFO:     127.0.0.1:38074 - "POST /answer HTTP/1.1" 200 OK
INFO:     127.0.0.1:60690 - "POST /answer HTTP/1.1" 200 OK
INFO:     Shutting down
INFO:     Waiting for connections to close. (CTRL+C to force quit)
INFO:     Waiting for background tasks to complete. (CTRL+C to force quit)
```

## Iteration 1

Just of the sake of this lab (since I don't have a separate VM with H100 GPU), I've lowered the RPS to 1.
Otherwise my whole setup just crashes.

**Optimization Parameters**: `--max-model-len 32768 --enable-chunked-prefill --max-num-batched-tokens 1024`

```json
{
  "requested_rps": 1.0,
  "duration_seconds": 300,
  "wall_clock_seconds": 360.02877819299465,
  "total_requests": 300,
  "achieved_rps": 0.8332667224706798,
  "ok": 285,
  "timeouts": 0,
  "http_errors": 0,
  "client_errors": 15,
  "latency_p50": 2.36193562799599,
  "latency_p95": 18.41356498299865,
  "latency_p99": 40.80446903296979,
  "latency_max": 108.32684229401639
}
```

Looking at LangFuse traces:

**langgraph_time_0**

Most of the time is spent waiting for the vLLM to return an answer. Therefore we need to optimize vLLM and/or how it's being queried.

## Iteration 2

Let's change the parameters like so:

**Optimization Parameters**: `--max-model-len 4096 --enable-prefix-caching --gpu-memory-utilization 0.9 --max-num-batched-tokens 4096 --max-num-seqs 64`

- `--max-model-len 4096` - lowering this value can allow model to fit more KV cachaes in GPU Memory
- `--enable-prefix-caching` - allows for prefixes to be cached and used from cache instead of computing them again
- `--gpu-memory-utilization 0.9` - tells vLLM to pre-allocate up to 90% of GPU memory
- `--max-num-batched-tokens 4096` - Caps tokens processed per scheduler step; higher value raises throughput but adds per-request latency
- `--max-num-seqs 64` - Limits concurrent in-flight sequences to avoid overcommitting GPU/KV cache

Result:
```json
{
  "requested_rps": 1.0,
  "duration_seconds": 300,
  "wall_clock_seconds": 347.4572116610361,
  "total_requests": 300,
  "achieved_rps": 0.8634156665387239,
  "ok": 283,
  "timeouts": 2,
  "http_errors": 0,
  "client_errors": 15,
  "latency_p50": 3.3251205009873956,
  "latency_p95": 26.99964486301178,
  "latency_p99": 42.623024174012244,
  "latency_max": 100.14663059503073
}
```

The resulting load test had similar results (even slightly worse).

## Iteration 3

Next thing to try:

- `--max-num-seqs 256` - max concurrent sequences per batch. Raising this increases throughput (better GPU utilization) but can hurt per-request latency since more requests compete for compute
- `--max-num-batched-tokens 16384` - caps total tokens processed per iteration. Higher = better throughput, but increases time-to-first-token for individual requests if the batch is dominated by long prefills 

**Optimization Parameters**: `--max-model-len 4096 --enable-prefix-caching --gpu-memory-utilization 0.9 --max-num-batched-tokens 16384 --max-num-seqs 256`

Result:
```json
{
  "requested_rps": 1.0,
  "duration_seconds": 300,
  "wall_clock_seconds": 360.03535742801614,
  "total_requests": 300,
  "achieved_rps": 0.8332514954728597,
  "ok": 287,
  "timeouts": 0,
  "http_errors": 0,
  "client_errors": 13,
  "latency_p50": 1.6353864410193637,
  "latency_p95": 13.296275467029773,
  "latency_p99": 18.63332071597688,
  "latency_max": 22.996435616980307
}
```

Increasing the `--max-num-seqs 256` did the job here, allowing fore more requests being handles in parallel.

---

## Final eval run


### Baseline eval run:

```json
"summary": {
  "total": 30,
  "passed": 8,
  "pass_rate": 0.26666666666666666,
  "average_iterations": 1.5,
  "passed_by_iteration": {
    "0": 6,
    "1": 8,
    "2": 8,
    "3": 8
  },
  "pass_rate_by_iteration": {
    "0": 0.2,
    "1": 0.26666666666666666,
    "2": 0.26666666666666666,
    "3": 0.26666666666666666
  }
}
```

### Final eval run

```json
"summary": {
  "total": 30,
  "passed": 10,
  "pass_rate": 0.3333333333333333,
  "average_iterations": 1.5666666666666667,
  "passed_by_iteration": {
    "0": 7,
    "1": 9,
    "2": 10,
    "3": 10
  },
  "pass_rate_by_iteration": {
    "0": 0.23333333333333334,
    "1": 0.3,
    "2": 0.3333333333333333,
    "3": 0.3333333333333333
  }
}
```

### Summary

The resulting vLLM config not only increase the throughput of the model but also increase the overall model accuracy. 
Which is a big win!
