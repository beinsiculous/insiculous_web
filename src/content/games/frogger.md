---
title: 'Insiculous Frogger'
blurb: 'Five conveyor lanes of carts, a soup river of rafts and sinking crackers, and a bun in a nest.'
status: 'playable'
wasm: '/games/frogger/v3/game.js'
editor: '/playground/frogger/v3/game.js'
width: 720
height: 768
screenshots: ['/images/chicken-coop-2026-09.png']
order: 6
---

A 13-row gauntlet: five conveyor lanes of carts, a sidewalk median, five soup
lanes ridden on celery and baguette rafts and crackers, and five nests.
Crackers sink after a warning; beat the timer, fill all five nests to clear
the round, then a one-second beat and everything speeds up. In Ridiculous mode the crackers sink
on staggered cycles and a bun periodically waits in a nest; enter while it's
there and you're lunch.

Game 6 of the series and the first built on the engine's tilemap component
— the board is four tilemap entities, one per tile sheet: the floor, the coop
wall, the soup and the conveyor belt. Two-chicken co-op, localized in English
and Pirate, chaos modes included.

Built on Insiculous 2D. Playable right here in the browser (WebGPU —
Chrome/Edge, or Firefox with `dom.webgpu.enabled`); desktop builds
(Vulkan / Metal / DX12) run the same code natively.
