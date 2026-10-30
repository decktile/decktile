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
