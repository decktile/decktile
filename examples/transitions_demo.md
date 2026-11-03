---
theme: default
paginate: true
title: Slide Transitions
transition: fade
---

@kicker Templates
@subtitle Press → to see each transition. Set a default in frontmatter, override per slide.

# Slide Transitions

@speaker name="decktile"

---

@transition fade

## fade

Opacity 0 → 1. This deck's default, set once in frontmatter with `transition: fade`.

::: grid {cols=3}
::: card{ tag="green" }
**Calm**
Good default for talks.
:::
::: card{ tag="cyan" }
**Subtle**
Never distracts from content.
:::
::: card{ tag="yellow" }
**Safe**
Works with any layout.
:::
:::

---

@transition slide

## slide

The new slide moves in from the right while it fades in.

- Feels like turning a page
- Good for step-by-step stories
- Reads as "next", so use it going forward

```markdown
@transition slide
```

---

@transition zoom

## zoom

The new slide grows from 85% to full size while it fades in.

::: grid {cols=3}
::: card{ tag="red", metric }
3×
Faster scheduling
:::
::: card{ tag="cyan", metric }
90%
GPU utilisation
:::
::: card{ tag="green", metric }
0
Code changes
:::
:::

Use it for a reveal: big numbers, a key result.

---

@transition wipe

## wipe

The new slide is revealed left to right.

| Before | After |
|--------|-------|
| One pod per GPU | Many pods share a GPU |
| Idle memory | Memory sliced per pod |
| Manual placement | Scheduler picks the GPU |

Good for before/after and comparisons.

---

@transition none

## none

No animation. Use it to switch off the deck default for one slide.

- Live demos and screenshots
- Slides you flip back and forth
- Anything that must appear instantly

```markdown
@transition none
```

---

## Cheat sheet

| Transition | Effect | Use for |
|------------|--------|---------|
| `fade` | Opacity 0 → 1 | Default |
| `slide` | Moves in from the right + fade | Stories, steps |
| `zoom` | Scale 0.85 → 1 + fade | Reveals, numbers |
| `wipe` | Left-to-right reveal | Comparisons |
| `none` | Instant | Demos, screenshots |

All transitions run 0.4s and only animate the incoming slide. PDF and ODP output ignore them.
