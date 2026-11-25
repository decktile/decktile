---
theme: .
size: 16:9
paginate: true
---

@kicker THEME_NAME
# Theme preview
@subtitle Edit theme.css and theme.toml, then rebuild this deck

---

## Text and lists

Body text with **bold**, *italic*, `code` and a [link](https://example.com).

- First point
- Second point

#### Section label

> A quote

---

## Cards

::: card {tag=green}
### Green
Tag colour
:::
::: card {tag=cyan}
### Cyan
Tag colour
:::
::: card {tag=yellow}
### Yellow
Tag colour
:::
::: card {tag=red}
### Red
Tag colour
:::

---

## Metrics

::: card {metric}
42%
Plain metric
:::
::: card {metric kpi}
1,800 Pods
Peak scale
Footnote line
:::
::: card {tile}
### {icon:cpu} Tile
Icon over caption
:::
::: card {plain}
### Plain
Column without a panel
:::

---

@layout two-col
@class cols-1-2

## Table and diagram

| Workload | Allocation |
|---|---|
| Inference | Shared |
| Training | Dedicated |

@col

```pdg
graph dir=LR
a "Request" .soft
b "Scheduler" .accent
c "GPU"
a -> b -> c .accent
```

---

@variant dark

## Dark variant

::: card {tag=cyan}
### Card on dark
Text
:::
::: card
### Default card
Text
:::

---

## Chart

```seaborn
import matplotlib.pyplot as plt
fig, ax = plt.subplots(figsize=(8, 3.5))
ax.bar(["A", "B", "C", "D"], [3, 5, 2, 4], color=[f"C{i}" for i in range(4)])
```
