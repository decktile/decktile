---
theme: default
paginate: true
title: Timeline Demo
---

@kicker Templates
@subtitle Vertical and horizontal timeline layouts

# Timeline Layouts

@speaker name="slidr"

---

@layout timeline-vertical

## Project Roadmap

::: grid {cols=1}
::: card {label="Q1"}
### Q1 2026
Kickoff and planning phase.
:::
::: card {focus, label="Q2"}
### Q2 2026
Major public launch -- the key milestone.
:::
::: card {label="Q3"}
### Q3 2026
Scale and iterate based on feedback.
:::
::: card {label="Q4"}
### Q4 2026
Expand to new markets.
:::
:::

<!--
Cards alternate left/right of a central vertical spine. ::: card {focus}
scales an item up and highlights it -- use it for the milestone that
matters most.
-->

---

@layout timeline-horizontal

## Release Timeline

::: grid {cols=4}
::: card {label="v1"}
### v1.0
Initial release
:::
::: card {focus, label="v2"}
### v2.0
Big feature launch
:::
::: card {label="v2.1"}
### v2.1
Bugfixes
:::
::: card {label="v3"}
### v3.0
Next major
:::
:::

<!--
Same idea, rotated: cards alternate above/below a horizontal spine.
Keep horizontal-timeline card text brief (a title plus one short line)
-- cards have a fixed height so the connector always reaches the spine.
-->
