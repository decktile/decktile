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
    db "Database" .green shape=cylinder
    api -> db
  }
  web, mobile -> api
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
