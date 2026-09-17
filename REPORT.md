# Report

## vLLM Configuration explanation

```shell
vllm serve Qwen/Qwen3-4B-Instruct-2507-FP8 --port 8000 --trust-remote-code --max-model-len 32768 --enable-chunked-prefill --max-num-batched-tokens 1024
```

- --trust-remote-code - Trusts custom python code shipped with the model
- --max-model-len 32768 - Caps the maximum context length, lowers GPU Mem usage
- --enable-chunked-prefill - Instead of processing on big promt in one go, vLLM splits it into multiple chunks, so long prompts don't block short generations from making progress.
- --max-num-batched-tokens 1024 -  Caps total number of tokens processed in a single scheduler iterations. With chunked prefill enabled, this is the main lever for balancing throughput vs. latency

---

## Kubernetes yaml config used to deploy model

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: vllm
  namespace: default
  labels:
    app: vllm
spec:
  replicas: 1
  selector:
    matchLabels:
      app: vllm
  template:
    metadata:
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8000"
        prometheus.io/path: "/metrics"
      labels:
        app: vllm
    spec:
      volumes:
      # PVC
      - name: cache-volume
        persistentVolumeClaim:
          claimName: vllm
      # vLLM needs to access the host's shared memory for tensor parallel inference.
      - name: shm
        emptyDir:
          medium: Memory
          sizeLimit: "8Gi"
      hostNetwork: true
      hostIPC: true
      containers:
      - name: vllm
        image: rocm/vllm:rocm7.13.0_gfx120X-all_ubuntu24.04_py3.13_pytorch_2.10.0_vllm_0.19.1
        securityContext:
          seccompProfile:
            type: Unconfined
          runAsGroup: 44
          capabilities:
            add:
            - SYS_PTRACE
        command: ["/bin/sh", "-c"]
        args: [
          "vllm serve Qwen/Qwen3-4B-Instruct-2507-FP8 --port 8000 --trust-remote-code --max-model-len 32768 --enable-chunked-prefill --max-num-batched-tokens 1024"
        ]
        env:
        - name: HF_TOKEN
          valueFrom:
            secretKeyRef:
              name: hf-token-secret
              key: token
        ports:
        - containerPort: 8000
        resources:
          limits:
            cpu: "10"
            #memory: 20G
            amd.com/gpu: "1"
          requests:
            cpu: "6"
            memory: 6G
            amd.com/gpu: "1"
        volumeMounts:
        - name: cache-volume
          mountPath: /root/.cache/huggingface
        - name: shm
          mountPath: /dev/shm
```