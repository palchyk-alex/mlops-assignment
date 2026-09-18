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

