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

---

@transition slide

## slide

The new slide moves in from the right while it fades in.

```markdown
@transition slide
```

---

@transition zoom

## zoom

The new slide grows from 85% to full size while it fades in.

```markdown
@transition zoom
```

---

@transition wipe

## wipe

The new slide is revealed left to right.

```markdown
@transition wipe
```

---

@transition none

## none

No animation. Use it to switch off the deck default for one slide.

```markdown
@transition none
```

---

## Cheat sheet

| Transition | Effect |
|------------|--------|
| `fade` | Opacity 0 → 1 |
| `slide` | Moves in from the right + fade |
| `zoom` | Scale 0.85 → 1 + fade |
| `wipe` | Left-to-right reveal |
| `none` | Instant |

All transitions run 0.4s and only animate the incoming slide. PDF and ODP output ignore them.
