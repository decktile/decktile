---
title: predictygraph Demo
---

# predictygraph

@kicker Readable diagrams inside slides

@speaker name="Decktile" role="Text-to-graph rendering"

---

## Architecture

@layout two-col

predictygraph draws diagrams from a
short text description. Nodes and edges
are placed automatically.

- Per-group layouts
- Groups as containers
- Tag colours from the theme
- CSS inside the diagram

@col

```pdg
graph dir=TB
group main {
  app "Application" .green
  mem "Memory" .cyan
  comp "Compute" .cyan
  gpu "GPU" .green
  app -> mem -> comp -> gpu
}
```

---

## Flowchart

@layout two-col

Flowcharts use decision diamonds and
process boxes with directional edges
to show logic flow.

- Box shapes for processes
- Diamond shapes for decisions
- Edge labels for branches

@col

```pdg
graph dir=TB
start "Start" .green
process "Process" .cyan
decision "Valid?" .yellow shape=diamond
done "Done" .green
retry "Retry" .red
start -> process -> decision
decision -> done "Yes"
decision -> retry "No"
retry -> process
```

---

## Groups

```pdg
graph dir=TB
group main "System Architecture" {
  group frontend "Frontend" dir=LR {
    web "Web App" .cyan
    mobile "Mobile" .cyan
  }
  group backend "Backend Services" {
    api "API" .cyan
    db "Database" .green shape=cylinder border=glow
    api -> db flow=both
  }
  web, mobile -> api flow=forward
}
```

---

## State Machine

@layout two-col

State machines model system behavior
with states and transitions. Each state
is a node with specific styling.

@col

```pdg
graph dir=LR
default node shape=circle
idle "Idle" .green
running "Running" .cyan
error "Error" .red
done "Done" .green
idle -> running "Start"
running -> error "Fail"
running -> done "OK"
error -> running "Retry"
done -> idle "Reset"
```

---

## Animated

@layout two-col

In the HTML deck, diagrams can move.
PDF and ODP get a clean still frame.

- `flow=` dots travel along an edge
- `border=pulse`, `march`, `glow`
- Set per edge, per node, or in CSS

@col

```pdg
graph dir=TB route=bend
user "User" .green border=pulse
gw "Gateway" .cyan border=march
sched "Scheduler" .cyan
gpu "GPU pool" .yellow shape=cylinder border=glow
user -> gw flow=forward
gw -> sched flow=forward flow-speed=0.8s
sched <-> gpu flow=both "allocate"
```

---

## Trunkline

Dual-path backbone: ortho routing, ring flows, a draw-in route and a background grid.

```pdg
graph dir=LR theme=trunkline route=ortho radius=0 diagonal=always grid=40 rank-gap=170 balance=center
dc "Data center" sub="GPU racks"
group fabric "Spine fabric" .rail layout=column gap=60 {
  spa "Spine A" sub="400G"
  spb "Spine B" sub="400G"
}
group svc .list layout=column align=start {
  obj "Object store" sub="S3 · 4 PB"
  train "Training cluster" sub="512 × H100"
  infer "Inference" sub="vLLM pool"
  feat "Feature store" sub="Redis"
  log "Logging" sub="Loki"
  peer "Peering" sub="IX · 2 × 100G"
}
dc -> spa "primary" .primary flow=forward flow-speed=.9s
dc -> spb "backup" .backup flow=forward flow-speed=1.4s
spa -> spb .primary flow=forward flow-speed=1.2s
spa -> obj, infer fan=spread stub=24
spa -> train .primary fan=spread stub=24 flow=draw flow-speed=2.5s
spb -> feat, log, peer fan=spread stub=24
```

---

## HAMi: a Pod's path to the GPU

```pdg
graph layout=row theme=hami gap=40 steps=auto
group panels layout=row align=stretch gap=40 .bare {
group cp "Control plane" sub="decides where the Pod runs" layout=column gap=30 {
  pod "Pod" sub="nvidia.com/gpumem: 3000"
  webhook "MutatingWebhook" sub="sets schedulerName" .blue
  sched "HAMi scheduler" sub="picks a node and a card" .blue
}
group node "GPU node" sub="sets up the container, enforces limits" layout=column gap=30 .green {
  kubelet "kubelet" sub="starts the Pod"
  plugin "HAMi device plugin" sub="mounts libvgpu.so" .green
  core "HAMi-Core" sub="checks memory and kernel calls" .green
}
}
gpu "GPU" border=glow
pod -> webhook flow=forward
webhook -> sched flow=forward
sched -> kubelet "bind" flow=forward
kubelet -> plugin "Allocate()" flow=forward
plugin -> core flow=forward
core -> gpu flow=forward
css { group.bare { fill: none; stroke: none; padding: 0; } }
```

---

## HAMi: where it sits in the GPU stack

@layout two-col

HAMi adds one piece to the scheduling layer and
leaves the rest of the NVIDIA stack alone.

- `align=stretch`: equal-width tiers
- `legend .hami "..."`: a key from classes

@col

```pdg
graph layout=column align=stretch gap=8 theme=hami
default group layout=row gap=10 .tier
group l5 "Kubernetes scheduling" {
  ks "kube-scheduler"
  hs "HAMi scheduler" .hami
  p "Pod"
}
group l4 "Container runtime" {
  c "containerd"
  t "NVIDIA Container Toolkit"
}
group l3 "User-space libraries" {
  cu "CUDA"
  nv "NVML"
  smi "nvidia-smi"
  dc "DCGM"
}
group l2 "Kernel driver" {
  ko "nvidia.ko"
  uvm "nvidia-uvm.ko"
}
group l1 "Hardware" {
  g "NVIDIA GPU"
  pc "PCIe"
  nl "NVLink"
}
legend .hami "HAMi component"
css {
  group.tier { fill: #ffffff; stroke: var(--border); title-fill: none; padding: 8px 12px; }
  node { font-weight: normal; padding: 5px 12px; }
  node.hami { fill: var(--green); stroke: var(--green); color: #ffffff; font-weight: 600; }
}
```

---

## HAMi: NVIDIA kernel modules

```pdg
graph layout=column align=stretch gap=8 theme=hami
group user "User space" layout=row gap=24 .space {
  nvml "libnvidia-ml.so" sub="NVML" align-x=nvidia .blue
  libcuda "libcuda.so" sub="CUDA driver API" align-x=uvm .blue
}
group kernel "Kernel space" layout=row gap=60 .kspace {
  nvidia "nvidia" sub="core GPU driver" .green
  uvm "nvidia_uvm" sub="unified memory" .green
}
group hw "Hardware" layout=row .space {
  gpu "NVIDIA GPU"
}
nvml -> nvidia
libcuda -> uvm "ioctl"
uvm -> nvidia "depends on"
nvidia -> gpu
bracket nvml, gpu "nvidia-smi needs\nthe whole path"
bracket nvidia, uvm "lsmod checks\nonly this layer"
css {
  group.space, group.kspace { label-position: left; title-fill: none; stroke: none; }
  group.space { fill: #eff6ff; color: var(--blue); }
  group.kspace { fill: #f0fdf4; color: var(--green); }
  node.blue, node.green { accent-bar: none; }
  node.blue { color: var(--blue); }
  node.green { color: var(--green); }
}
```
