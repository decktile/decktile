---
title: Seaborn Demo
---

# Seaborn

@kicker Data visualization with Python

@speaker name="Decktile" role="Code-to-image rendering"

---

## Scatter Plot

```seaborn
tips = sns.load_dataset("tips")
sns.scatterplot(data=tips, x="total_bill", y="tip", hue="day")
```

---

## Bar Plot

```seaborn
penguins = sns.load_dataset("penguins")
sns.barplot(data=penguins, x="species", y="body_mass_g", hue="sex")
```

---

## Memory Oversubscription

```seaborn
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

fig, ax = plt.subplots(figsize=(8, 2.8))

card_color = plt.rcParams["axes.facecolor"]
fg = plt.rcParams["text.color"]
dimmed = plt.rcParams["xtick.color"]
cmap = plt.get_cmap("Paired")
danger = cmap(4.5 / 12)     # muted red
danger_bright = cmap(5 / 12)  # bright red for labels
elastic = cmap(2.5 / 12)   # green
base = cmap(0.5 / 12)      # light blue
ax.set_facecolor("none")
fig.patch.set_facecolor(card_color)

ax.barh(1, 8, color=base, height=0.65)
ax.barh(1, 3, left=8, color=danger, height=0.65)
ax.plot([10, 10], [0.62, 1.38], color=danger, linewidth=2.5, solid_capstyle="butt")

ax.barh(0, 8, color=base, height=0.65)
ax.barh(0, 7, left=8, color=elastic, height=0.65)
ax.plot([10, 10], [-0.38, 0.38], color=fg, linewidth=1.5, linestyle="--")
ax.plot([15, 15], [-0.38, 0.38], color=fg, linewidth=1.5, linestyle="--")

ax.set_xlim(0, 15.2)
ax.spines[["top", "right", "left", "bottom"]].set_visible(False)
ax.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)

# Bar labels beside bars
ax.text(-0.3, 1, "Without HAMi", ha="right", va="center", fontsize=10, color=fg, fontweight="bold")
ax.text(-0.3, 0, "With HAMi:\nElastic Scaling", ha="right", va="center", fontsize=10, color=fg, fontweight="bold")

# Bar 1 annotations
ax.text(4, 1, "Normal base load", ha="center", va="center", fontsize=9, color=fg, fontweight="bold")
ax.text(9.5, 1, "Traffic spike", ha="center", va="center", fontsize=7.5, color=dimmed, fontweight="bold")
ax.text(10, 1.42, "10 GB limit", ha="center", va="bottom", fontsize=8, color=danger_bright, fontweight="bold")

# Bar 2 annotations
ax.text(4, 0, "Normal base load", ha="center", va="center", fontsize=9, color=fg, fontweight="bold")
ax.text(11.5, 0, "Traffic spike", ha="center", va="center", fontsize=7.5, color=dimmed, fontweight="bold")
ax.text(10, -0.42, "10 GB\nsoft limit", ha="center", va="top", fontsize=7.5, color=dimmed)
ax.text(15, -0.42, "15 GB\nburst", ha="center", va="top", fontsize=7.5, color=dimmed)

# Legend
legend_patches = [
    mpatches.Patch(color=base, label="Base load"),
    mpatches.Patch(color=danger, label="Traffic spike (OOM risk)"),
    mpatches.Patch(color=elastic, label="Traffic spike (elastic)"),
]
ax.legend(handles=legend_patches, loc="upper center", bbox_to_anchor=(0.5, 0.07), fontsize=8, ncol=3, framealpha=0.8)
```

---

## Heatmap

```seaborn
flights = sns.load_dataset("flights")
flights_pivot = flights.pivot(index="month", columns="year", values="passengers")
sns.heatmap(flights_pivot, annot=True, fmt="d", cmap="YlOrRd")
```

---

## Distribution

@layout two-col

```seaborn
iris = sns.load_dataset("iris")
sns.boxplot(data=iris, x="species", y="sepal_length")
```

@col

- Seaborn builds on matplotlib
- Tight integration with pandas DataFrames
- Statistical visualizations out of the box
- Auto-generated from fenced code blocks

---

# Explainer charts

@kicker Hand-drawn matplotlib, from a real talk

---

## Priority Preemption

@subtitle High priority pauses low priority at kernel boundaries

High-priority tasks preempt low-priority ones at CUDA kernel boundaries: no wasted compute, clean context switch:

:::card
```seaborn
import matplotlib.pyplot as plt

fig, ax = plt.subplots(figsize=(8, 2.8))

fg = plt.rcParams["text.color"]
dimmed = plt.rcParams["xtick.color"]
cmap = plt.get_cmap("Paired")
green = cmap(2.5 / 12)
blue = cmap(0.5 / 12)
red = cmap(4.5 / 12)
grey = "#9ca3af"
sleep_bg = "#374151"

ax.set_facecolor("none")
fig.patch.set_alpha(0)

# Top: IDLE(25) + EXECUTING(50) + IDLE(25)
ax.barh(1, 25, color=grey, height=0.65)
ax.barh(1, 50, left=25, color=green, height=0.65)
ax.barh(1, 25, left=75, color=grey, height=0.65)

# Bottom: EXECUTING(25) + SLEEP(50) + EXECUTING(25)
ax.barh(0, 25, color=blue, height=0.65)
ax.barh(0, 50, left=25, color=sleep_bg, height=0.65)
ax.barh(0, 25, left=75, color=blue, height=0.65)

# Segment dividers
for x in [25, 75]:
    ax.plot([x, x], [0.62, 1.38], color=fg, linewidth=0.8, linestyle="--")
    ax.plot([x, x], [-0.38, 0.62], color=fg, linewidth=0.8, linestyle="--")

ax.set_xlim(0, 100)
ax.spines[["top", "right", "left", "bottom"]].set_visible(False)
ax.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)

# Side labels
ax.text(0, 1.38, "HIGH PRIORITY", ha="left", va="bottom", fontsize=10, color=green, fontweight="bold")
ax.text(0, 0.38, "LOW PRIORITY", ha="left", va="bottom", fontsize=10, color=blue, fontweight="bold")

# Top bar labels
ax.text(12.5, 1, "IDLE", ha="center", va="center", fontsize=9, color=fg)
ax.text(50, 1, "EXECUTING", ha="center", va="center", fontsize=9, color=fg, fontweight="bold")
ax.text(87.5, 1, "IDLE", ha="center", va="center", fontsize=9, color=fg)

# Bottom bar labels
ax.text(12.5, 0, "EXECUTING", ha="center", va="center", fontsize=9, color=fg)
ax.text(50, 0, "SLEEP", ha="center", va="center", fontsize=9, color=red, fontweight="bold")
ax.text(87.5, 0, "EXECUTING", ha="center", va="center", fontsize=9, color=fg)

ax.text(50, -0.35, "CUDA-KERNEL BOUNDARY", ha="center", va="top", fontsize=7, color=red)
```
:::

---

## The Problem We Measured

@subtitle Asking for a GPU is not the same as using it


Two real jobs. Each one held **a whole H200, 141 GB**:

```seaborn
import matplotlib.pyplot as plt

FG, DIM = "#3a2020", "#7a6a5a"
RED, YELLOW, GREY = "#e61e24", "#f4a93a", "#e0e0df"

fig, ax = plt.subplots(figsize=(10.5, 3.0))
ax.set_facecolor("none")
fig.patch.set_alpha(0)

ax.text(-40, 1.75, "GPU MEMORY  -  ALLOCATED VS USED", fontsize=10.5, color=DIM, family="monospace")

ax.barh(1, 141, color=GREY, height=0.5)
ax.barh(1, 1, color=RED, height=0.5)
ax.barh(0, 141, color=GREY, height=0.5)
ax.barh(0, 39, color=YELLOW, height=0.5)

ax.text(-4, 1, "Time-series\n(inference)", ha="right", va="center", fontsize=12.5, color=FG, fontweight="bold", linespacing=1.4)
ax.text(-4, 0, "Defect detection\n(training)", ha="right", va="center", fontsize=12.5, color=FG, fontweight="bold", linespacing=1.4)

ax.text(6, 1, "1 GB used  -  SM 16-18%", ha="left", va="center", fontsize=12, color=FG)
ax.text(44, 0, "39 GB used", ha="left", va="center", fontsize=12, color=FG)

ax.text(141, 1.42, "one whole H200 = 141 GB", ha="right", va="bottom", fontsize=11, color=DIM)

ax.annotate("", xy=(139, -0.55), xytext=(41, -0.55),
            arrowprops=dict(arrowstyle="<->", color=DIM, linewidth=1.4))
ax.text(90, -0.74, "100 GB free  →  inference  -  notebooks  -  CV / embedding",
        ha="center", va="top", fontsize=11, color=FG, fontweight="bold")

ax.set_xlim(-40, 148)
ax.set_ylim(-1.15, 1.95)
ax.spines[["top", "right", "left", "bottom"]].set_visible(False)
ax.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)
ax.set_xticks([])
```

- The time-series job leaves **140 GB and 80% of the GPU** doing nothing
- Detection training took **39 GB** - it still left most of the card unused
- **Many of our GPUs have no MIG:** L40, L40S, A6000, ...

> Kubernetes gives you one choice: `nvidia.com/gpu: 1`. The whole card, or nothing.

---

## The Result: 3.4x More Work Per GPU

@subtitle Fix the SLA, scale replicas, fill the empty GPU


```seaborn
import matplotlib.pyplot as plt

FG, DIM = "#3a2020", "#7a6a5a"
RED, GREEN, GREY = "#e61e24", "#39ae4a", "#e0e0df"

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.5, 3.0),
                               gridspec_kw={"width_ratios": [1.3, 1], "wspace": 0.32})
fig.patch.set_alpha(0)
for ax in (ax1, ax2):
    ax.set_facecolor("none")
    ax.spines[["top", "right", "left", "bottom"]].set_visible(False)
    ax.tick_params(left=False, labelleft=False, bottom=False, labelbottom=False)
    ax.set_xticks([])

# ---- left: throughput, labels to the LEFT so nothing overlaps the line ----
ax1.text(-42, 2.9, "REQ/S PER CARD  @  P95 160 MS", fontsize=10.5, color=DIM, family="monospace")
for y, v, n, c in [(2, 20.7, "Native", GREY), (0, 71.1, "HAMi + KEDA", RED)]:
    ax1.barh(y, v, color=c, height=0.62)
    ax1.text(-3, y, n, ha="right", va="center", fontsize=12, color=FG, fontweight="bold")
    ax1.text(v + 3, y, str(v), ha="left", va="center", fontsize=12.5, color=FG, fontweight="bold")
ax1.plot([20.7, 20.7], [-0.5, 2.5], color=DIM, linewidth=1.2, linestyle=(0, (4, 3)))
ax1.text(20.7, 2.55, "one whole GPU", ha="center", va="bottom", fontsize=10.5, color=DIM)
ax1.text(-3, -0.55, "3.4x per card", ha="right", va="center", fontsize=11.5, color=RED, fontweight="bold")
ax1.set_xlim(-42, 100)
ax1.set_ylim(-0.9, 3.1)

# ---- right: SM utilization ----
ax2.text(-0.15, 128, "SM UTILIZATION VS REPLICAS", fontsize=10.5, color=DIM, family="monospace")
xs, vals = [0, 1, 2, 3], [18, 31, 54, 100]
ax2.plot(xs, vals, color=RED, linewidth=2.2, zorder=2)
for x, v, c, r in zip(xs, vals, [GREY, RED, RED, GREEN], [7, 5.5, 5.5, 9]):
    ax2.plot(x, v, "o", markersize=r, color=c, markeredgecolor="white", markeredgewidth=1.3, zorder=3)
    ax2.text(x, v + 8, f"{v}%", ha="center", fontsize=11.5, color=FG, fontweight="bold")
for x, lab in zip(xs, ["1", "2", "5", "10 replica"]):
    ax2.text(x, -13, lab, ha="center", fontsize=12, color=DIM)
ax2.set_xlim(-0.35, 3.4)
ax2.set_ylim(-22, 140)
```

One pod uses only **18% of the card**. Pack **10 replicas** on it and the GPU hits **100%** - same latency.

- **HAMi does not make one pod faster** - it fills the GPU that was sitting empty
- Bigger batches did not help either: **32 to 512**, GPU still 7-10%
- Same 71 req/s (H200): **1 GPU instead of 3.4** → **~71% fewer cards**, **~51% less power**, **~$7k/month** at an example $4/GPU-h

---

## One Card, One Day

@subtitle One slice guaranteed, on purpose - and what it costs


**Workload:** an AI Notebook training YOLO11 - ~17k images, batch 64 → **39 GB** used. Batch is sized for **accuracy**, not to fill the card - so the spare **~100 GB is genuinely free**, not just idle. We fence **~30%** and cap the notebook to **70% of the cores**.

```seaborn
import matplotlib.pyplot as plt

FG, DIM = "#3a2020", "#7a6a5a"
RED, GREY = "#e61e24", "#eceae8"

fig, ax = plt.subplots(figsize=(5.2, 2.85))
fig.patch.set_alpha(0)
ax.set_facecolor("none")
ax.spines[["top", "right", "left", "bottom"]].set_visible(False)
ax.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)
ax.set_xticks([])

ax.text(-0.55, 104, "PRICE OF CAPPING", fontsize=11.5, color=DIM, family="monospace")
ax.plot([-0.5, 1.55], [60, 60], color=DIM, linewidth=1.2, linestyle=(0, (4, 3)), zorder=3)
ax.bar(0, 60, width=0.5, color=GREY, zorder=2)
ax.bar(1, 80, width=0.5, color=RED, zorder=2)
ax.text(0, 63, "1h00", ha="center", va="bottom", fontsize=15, color=FG, fontweight="bold")
ax.text(1, 83, "1h20", ha="center", va="bottom", fontsize=15, color=FG, fontweight="bold")
ax.text(1.34, 70, "+20 min", ha="left", va="center", fontsize=13, color=RED, fontweight="bold")
ax.text(0, -8, "full", ha="center", va="top", fontsize=12, color=DIM)
ax.text(1, -8, "70% cores", ha="center", va="top", fontsize=12, color=DIM)
ax.set_xlim(-0.8, 2.5)
ax.set_ylim(-20, 112)
```

- {icon:lock cls=accent-primary} **Memory is fenced.** The notebook sees only its own slice - it cannot OOM the neighbours
- {icon:gauge cls=accent-primary} **Cores are capped** with `force` - the freed share is **reserved**, not "maybe"
- {icon:refresh-cw cls=accent-contrast} **The price:** ~20 minutes, on purpose - *a small model; a big one costs much more*

---

## The Rest Follows The Load

@subtitle One notebook fixed all day - inference flexes by the hour


```seaborn
import matplotlib.pyplot as plt

FG, DIM = "#3a2020", "#7a6a5a"
BLUE, BLUEL, RED, YELLOW, GREY = "#28a4db", "#8fcdec", "#e61e24", "#f4a93a", "#eceae8"

fig, ax = plt.subplots(figsize=(11, 3.35))
fig.patch.set_alpha(0)
ax.set_facecolor("none")
ax.spines[["top", "right", "left", "bottom"]].set_visible(False)
ax.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)
ax.set_xticks([])

ax.text(-26, 2.86, "ONE H200 ACROSS ONE DAY", fontsize=11.5, color=DIM, family="monospace")
rows = [
    (2, "Morning", [(30, BLUE, "Notebook ~30%"), (50, RED, "Time-series  ×6"), (20, GREY, "")]),
    (1, "Office hours", [(30, BLUE, "Notebook ~30%"), (8, RED, "×1"), (42, YELLOW, "LLM inference  ×5"), (20, GREY, "")]),
    (0, "Night", [(30, BLUE, "Notebook ~30%"), (42, BLUEL, "more training"), (8, RED, "×1"), (20, GREY, "")]),
]
for y, label, segs in rows:
    left = 0
    for w, c, txt in segs:
        ax.barh(y, w, left=left, color=c, height=0.62, edgecolor="white", linewidth=1.8)
        if txt:
            ax.text(left + w / 2, y, txt, ha="center", va="center", fontsize=10.5,
                    color="#161616" if c in (YELLOW, BLUEL) else "white", fontweight="bold")
        left += w
    ax.text(-3, y, label, ha="right", va="center", fontsize=13, color=FG, fontweight="bold")
ax.text(100, 2.7, "card full", ha="right", va="bottom", fontsize=10, color=DIM)
ax.plot([100, 100], [-0.4, 2.58], color=DIM, linewidth=1.0, linestyle=(0, (2, 3)), zorder=1)
ax.set_xlim(-26, 106)
ax.set_ylim(-0.6, 3.2)
```

- {icon:lock cls=accent-primary} **The notebook never moves.** Its slice is fixed all day → training stays stable and guaranteed
- {icon:refresh-cw cls=accent-contrast} **KEDA hands the freed space off through the day.** The morning **burst fades** → cores go to **LLM <20B** → one time-series instance stays for scattered load → at night, spare **auto-scales more notebooks** for extra overnight training. *Never idle.*

---

@hidden
## Stable While Shared

@subtitle Does sharing make training jittery? We measured it


The card is now *truly* shared - the notebook trains while **bursty inference** flexes beside it. Does that shake the training? We measured epoch-time **CV** - standard deviation ÷ mean, lower is steadier.

```seaborn
import matplotlib.pyplot as plt

FG, DIM = "#3a2020", "#7a6a5a"
RED, GREEN = "#e61e24", "#39ae4a"

fig, ax = plt.subplots(figsize=(5.6, 2.95))
fig.patch.set_alpha(0)
ax.set_facecolor("none")
ax.spines[["top", "right", "left", "bottom"]].set_visible(False)
ax.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)
ax.set_xticks([])

ax.text(-0.55, 23.2, "EPOCH-TIME JITTER  (CV, LOWER = STEADIER)", fontsize=10, color=DIM, family="monospace")
bars = [(0, 1, GREEN, "alone"), (1, 19, RED, "shared, no cap"), (2, 9, GREEN, "shared, capped")]
for x, v, c, lab in bars:
    ax.bar(x, v, width=0.56, color=c, zorder=2)
    ax.text(x, v + 0.8, f"{v}%", ha="center", va="bottom", fontsize=15, color=FG, fontweight="bold")
    ax.text(x, -1.4, lab, ha="center", va="top", fontsize=11.5, color=DIM)
ax.annotate("", xy=(1.82, 10.2), xytext=(1.18, 17.6),
            arrowprops=dict(arrowstyle="->", color=FG, linewidth=1.7, connectionstyle="arc3,rad=-0.32"))
ax.text(2.02, 15.0, "cap halves it", ha="center", va="center", fontsize=10.5, color=FG, fontweight="bold")
ax.set_xlim(-0.65, 2.7)
ax.set_ylim(-4, 24.5)
```

- {icon:check cls=accent-primary} **Alone, nothing contends:** CV ~**1%** - rock-steady epochs
- {icon:triangle-alert cls=accent-secondary} **Shared with bursty inference, no cap:** CV jumps to **19%** - jittery, hard to predict
- {icon:gauge cls=accent-primary} **Cap the neighbours (`force`):** CV back to **9%** - steady again, same shared card

> **Honest caveat:** cap isolates *stability*, not *throughput* - for hard throughput isolation, use **MIG**.

---

## Memory Slicing

@subtitle Carve unused memory into per-pod slices


::: card
```seaborn
import matplotlib.pyplot as plt

fg = plt.rcParams["text.color"]
dimmed = plt.rcParams["xtick.color"]
cmap = plt.get_cmap("Paired")
red = cmap(4.5 / 12)
yellow = cmap(6.5 / 12)
grey = "#eceae8"

fig, ax = plt.subplots(figsize=(9.5, 2.9))
ax.set_facecolor("none")
fig.patch.set_alpha(0)

ax.text(-4, 1.75, "GPU MEMORY: ALLOCATED VS USED", fontsize=10.5, color=dimmed, family="monospace")

ax.barh(1, 141, color=grey, height=0.5)
ax.barh(1, 1, color=red, height=0.5)
ax.barh(0, 141, color=grey, height=0.5)
ax.barh(0, 39, color=yellow, height=0.5)

ax.text(-4, 1, "Inference\njob", ha="right", va="center", fontsize=12, color=fg, fontweight="bold", linespacing=1.4)
ax.text(-4, 0, "Training\njob", ha="right", va="center", fontsize=12, color=fg, fontweight="bold", linespacing=1.4)

ax.text(6, 1, "1 GB used", ha="left", va="center", fontsize=11.5, color=fg)
ax.text(44, 0, "39 GB used", ha="left", va="center", fontsize=11.5, color=fg)

ax.text(141, 1.42, "one whole H200 = 141 GB", ha="right", va="bottom", fontsize=10.5, color=dimmed)

ax.annotate("", xy=(139, -0.55), xytext=(41, -0.55),
            arrowprops=dict(arrowstyle="<->", color=dimmed, linewidth=1.4))
ax.text(90, -0.74, "~100 GB free: sliced per pod",
        ha="center", va="top", fontsize=10.5, color=fg, fontweight="bold")

ax.set_xlim(-4, 148)
ax.set_ylim(-1.15, 1.95)
ax.spines[["top", "right", "left", "bottom"]].set_visible(False)
ax.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)
ax.set_xticks([])
```
:::

- One job holds a whole card: 1 GB used of 141 GB
- Slicing frees the rest: MiB-level partitions per pod

---

## Compute Slicing

@subtitle Percent of compute per pod, enforced on every call


::: card
```seaborn
import matplotlib.pyplot as plt

fg = plt.rcParams["text.color"]
dimmed = plt.rcParams["xtick.color"]
cmap = plt.get_cmap("Paired")
green = cmap(2.5 / 12)
grey = "#9ca3af"

fig, ax = plt.subplots(figsize=(9, 2.7))
ax.set_facecolor("none")
fig.patch.set_alpha(0)

units, assigned = 8, 2
ax.bar(range(units), [1] * units, width=0.85,
       color=[green] * assigned + [grey] * (units - assigned),
       edgecolor="white", linewidth=1.5)

for u in range(units):
    ax.text(u, -0.18, str(u + 1), ha="center", va="top", fontsize=9.5, color=dimmed)

ax.annotate("", xy=(-0.35, -0.75), xytext=(1.35, -0.75),
            arrowprops=dict(arrowstyle="<->", color=fg, linewidth=1.4))
ax.text(0.5, -1.05, "pod A: 2 of 8 units = 25%", ha="center", va="top",
        fontsize=11.5, color=fg, fontweight="bold")
ax.text(4.5, -1.05, "6 units free for other pods", ha="center", va="top",
        fontsize=11.5, color=fg, fontweight="bold")

ax.text(-0.55, 1.75, "COMPUTE UNITS: 8 ON THE DEVICE, 2 ASSIGNED TO POD A",
        fontsize=10, color=dimmed, family="monospace")

ax.set_xlim(-0.6, 7.6)
ax.set_ylim(-1.5, 2.2)
ax.spines[["top", "right", "left", "bottom"]].set_visible(False)
ax.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)
ax.set_xticks([])
```
:::

- Each pod gets a fixed % of the device's compute units
- Hard ceiling on every kernel launch: no bursting above the slice
- Unused units stay free for other pods

---

## Time Slicing

@subtitle Workloads take turns at kernel boundaries


::: card
```seaborn
import matplotlib.pyplot as plt

fg = plt.rcParams["text.color"]
dimmed = plt.rcParams["xtick.color"]
cmap = plt.get_cmap("Paired")
green = cmap(2.5 / 12)
grey = "#9ca3af"

fig, ax = plt.subplots(figsize=(9, 3.1))
ax.set_facecolor("none")
fig.patch.set_alpha(0)

for i, name in enumerate(["Agent A", "Agent B", "Agent C", "Agent D"]):
    y = 3 - i
    for q in range(4):
        color = green if q == i else grey
        ax.barh(y, 25, left=q * 25, color=color, height=0.6)
    ax.text(-4, y, name, ha="right", va="center", fontsize=11, color=fg, fontweight="bold")
    ax.text(i * 25 + 12.5, y, "EXECUTING", ha="center", va="center", fontsize=9, color=fg, fontweight="bold")

for x in [25, 50, 75]:
    ax.plot([x, x], [-0.5, 3.5], color=fg, linewidth=0.8, linestyle="--")

ax.text(50, 3.85, "TIME SLICING: ONE DEVICE, FOUR SLICES",
        ha="center", fontsize=10.5, color=dimmed, family="monospace")
ax.text(106, -0.75, "time ->", ha="right", va="top", fontsize=9, color=dimmed)

ax.set_xlim(-6, 106)
ax.set_ylim(-1.0, 4.1)
ax.spines[["top", "right", "left", "bottom"]].set_visible(False)
ax.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)
ax.set_xticks([])
```
:::

- Rotate compute access over time
- Kernel boundary is the switch point: no mid-kernel preemption
- Preemption optional: without it, long kernels run to completion

---

## Hardware Partitioning

@subtitle Fixed slots, strongest isolation, least flexible


::: card
```seaborn
import matplotlib.pyplot as plt

fg = plt.rcParams["text.color"]
dimmed = plt.rcParams["xtick.color"]
cmap = plt.get_cmap("Paired")
blue = cmap(0.5 / 12)
green = cmap(2.5 / 12)
orange = cmap(6.5 / 12)
grey = "#9ca3af"

fig, ax = plt.subplots(figsize=(8, 2.8))
ax.set_facecolor("none")
fig.patch.set_alpha(0)

for left, w, c, lab in [(0, 50, blue, "1/2 card"), (50, 25, green, "1/4 card"), (75, 25, orange, "1/4 card")]:
    ax.barh(1, w, left=left, color=c, height=0.65)
    ax.text(left + w / 2, 1, lab, ha="center", va="center", fontsize=9, color=fg, fontweight="bold")

ax.barh(0, 40, left=0, color=grey, height=0.65)
ax.barh(0, 35, left=40, color=grey, height=0.65)
ax.barh(0, 25, left=75, color=grey, height=0.65)
for x in [40, 75]:
    ax.plot([x, x], [-0.38, 0.62], color=fg, linewidth=1.2, linestyle="--")
for x, lab in [(20, "40%"), (57.5, "35%"), (87.5, "25%")]:
    ax.text(x, 0, lab, ha="center", va="center", fontsize=9, color=fg, fontweight="bold")

ax.text(0, 1.38, "HARDWARE PARTITIONS:  MIG, SR-IOV, vXPU, vDCU", ha="left", va="bottom", fontsize=10, color=fg, fontweight="bold")
ax.text(0, 0.38, "SOFTWARE PARTITIONS:  HAMi slices", ha="left", va="bottom", fontsize=10, color=fg, fontweight="bold")

ax.set_xlim(0, 100)
ax.spines[["top", "right", "left", "bottom"]].set_visible(False)
ax.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)
```
:::

- MIG, SR-IOV, vXPU, vDCU: hardware partitions, silicon-enforced
- Memory and compute fenced per slot: strongest isolation
