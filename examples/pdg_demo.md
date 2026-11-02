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

## HAMi: a Pod's path to the GPU

```pdg
graph layout=row theme=hami gap=40 steps=auto
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
gpu "GPU"
pod -> webhook
webhook -> sched
sched -> kubelet "bind"
kubelet -> plugin "Allocate()"
plugin -> core
core -> gpu
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

@layout two-col

`nvidia-smi` needs the whole path; `lsmod` only checks the kernel layer.

- `nvidia_uvm` is needed by compute workloads
- `nvidia_modeset` and `nvidia_drm` drive the display

@col

```pdg
graph layout=column align=stretch gap=8 theme=hami
group user "User space" layout=row gap=24 .space {
  nvml "libnvidia-ml.so" sub="NVML" .blue
  libcuda "libcuda.so" sub="CUDA driver API" .blue
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
uvm -> nvidia "depends"
nvidia -> gpu
css {
  group.space { fill: #eff6ff; stroke: none; title-fill: none; }
  group.kspace { fill: #f0fdf4; stroke: none; title-fill: none; }
  node.blue, node.green { accent-bar: none; }
  node.blue { color: var(--blue); }
  node.green { color: var(--green); }
}
```
