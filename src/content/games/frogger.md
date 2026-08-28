---
title: 'Insiculous Frogger'
blurb: 'Five lanes of traffic, five of water, diving turtles — and a crocodile in the home row.'
status: 'playable'
wasm: '/games/frogger/v2/game.js'
width: 720
height: 768
screenshots: []
order: 6
---

A 13-row gauntlet: five traffic lanes, a median, five water lanes, five home
slots. Ride logs and turtles, beat the timer, fill all five homes to clear
the round — then everything speeds up. In Ridiculous mode, the turtles dive
on staggered cycles and a crocodile periodically guards a home slot; enter
while it's surfaced and you're lunch.

Game 6 of the series and the first built on the engine's tilemap component
— the entire board is a single tilemap entity. Two-frog co-op, localized in
English and Pirate, chaos modes included.

Built on Insiculous 2D. Playable right here in the browser (WebGPU —
Chrome/Edge, or Firefox with `dom.webgpu.enabled`); desktop builds
(Vulkan / Metal / DX12) run the same code natively.
