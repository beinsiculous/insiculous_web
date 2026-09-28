---
title: 'Insiculous Snake'
blurb: 'Frank the bratwurst dachshund loose in the kitchen, growing longer with every snack — and a versus mode where two dogs share the floor.'
status: 'playable'
wasm: '/games/snake/v4/game.js'
editor: '/playground/snake/v4/game.js'
screenshots: ['/images/bratdog-2026-09.png']
order: 4
---

You are Frank, a bratwurst that is also a dachshund, loose on a kitchen
floor ringed by the counter's edge. Every snack he eats — a pretzel, a cheese
bite or a bacon bone — makes him one piece longer, and he bends round every
corner you steer him through. Run into the counter or bite your own tail and
he goes down in a daze.

Snake on a 24×15 grid with input buffering two turns ahead, so fast play
never eats your inputs. No physics engine underneath — the whole game is
pure grid math.

The twist is the **two-player versus mode**: Frank and a darker second dog
share one kitchen, and every death has a cause — the counter, a self-bite,
the other dog, or a head-on crash — so the game resolves a winner or a draw
accordingly. In **Ridiculous**, and its faster sibling **Insiculous**, the
counter's edge opens up and wraps around, with two snacks on the floor. Nine achievements, chaos modes included.

Built on Insiculous 2D. Playable right here in the browser (WebGPU —
Chrome/Edge, or Firefox with `dom.webgpu.enabled`); desktop builds
(Vulkan / Metal / DX12) run the same code natively.
