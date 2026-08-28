---
title: 'Insiculous Snake'
blurb: 'Grid snake with buffered turns — and a versus mode where head-on collisions have rules.'
status: 'playable'
wasm: '/games/snake/v2/game.js'
screenshots: []
order: 4
---

Snake on a 26×16 grid with input buffering two turns ahead, so fast play
never eats your inputs. No physics engine underneath — the whole game is
pure grid math.

The twist is the **two-player versus mode**: every death has a cause — wall,
self-bite, the other snake, or a head-on crash — and the game resolves
a winner or a draw accordingly. Thirteen achievements, chaos modes included.

Built on Insiculous 2D. Playable right here in the browser (WebGPU —
Chrome/Edge, or Firefox with `dom.webgpu.enabled`); desktop builds
(Vulkan / Metal / DX12) run the same code natively.
