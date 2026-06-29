# Shiny Component Shorts

A small repo for generating 30-second “Did you know?” videos about Shiny components.

The goal is simple:

> One Shiny component. One hidden feature. One tiny app.

## What this repo does

This repo contains agent skills for creating:

* Short Shiny mini-apps
* 30-second video storyboards
* Narration scripts
* Recording notes
* Python or R examples

The focus is not full tutorials. Each video should reveal one useful, surprising behavior in a component.

## Repo structure

```text
.
├── .claude/
│   └── skills/
│       └── shiny-component-shorts/
│           └── SKILL.md
├── .agents/
│   └── skills/
│       └── shiny-component-shorts/
│           └── SKILL.md
├── examples/
│   ├── py/
│   └── r/
├── CLAUDE.md
├── AGENTS.md
└── README.md
```

## Using with Claude Code

Run:

```text
/shiny-component-shorts toolbar-select in Python
```

Example:

```text
/shiny-component-shorts Create 5 did-you-know video ideas for Shiny data grid. Include runnable mini apps.
```

## Using with Codex

Run:

```text
Use $shiny-component-shorts to create 5 mini-app video ideas for Shiny toolbar-select in Python.
```

## Video format

Each idea should include:

* Hook
* Hidden feature
* Mini-app concept
* Variations
* 30-second storyboard
* Runnable code
* Recording notes

## Default style

Good:

> “Did you know a Shiny table can become an input?”

Bad:

> “Introduction to Shiny data grids.”

## Rule of thumb

If the viewer says, “Wait, that component can do that?” then the idea works.
