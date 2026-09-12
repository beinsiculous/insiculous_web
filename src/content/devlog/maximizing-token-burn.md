---
title: 'The Fable 5.1 Code Cleanup Refactor'
description: 'A 36-hour window before a weekly reset became a ten-batch refactor test for Fable, Kimi, and Gemini across the engine codebase.'
pubDate: 2026-09-03
author: Jesse
tags: ['refactor', 'workflow', 'review', 'models']
---

It's like the craziness just don't stop. It felt like in one day we got the Google Gemini 3.8 Flash model drop, and alongside that, the Fable 5.1 drop with a usage reset from Anthropic! I noticed my sub's token reset later on Tuesday, giving me a 36-hour window before 8 AM’s weekly reset on Thursday. I figured it was a great chance to maximize my token burn and see what Fable 5.1 was capable of.

My typical move when testing out a new model is pointing it at insiculous_2d and having it audit the codebase for DRY, SRP, and KISS violations - as well as clean up any dead / useless unit or integration tests. This time around, I also added in a line about renaming all variables, files, and folders to be human-readable and represent what their function is. I did this because I'd noticed there were lots of block comments and an occasional file or variable that was a non-straightforward acronym. I really wanted my AI-generated code to read more like the way I write code, instead of its over-sharing comment standard.  

It ended up making a very detailed plan grouped by a set of 10 batches of code changes that it wanted to run through. I ran my adversarial review; Kimi K3 provided some thoughtful feedback, which Fable folded in immediately, and then requested a second review from Kimi! After the plan was set, Fable took an axe to a majority of the tests that I had in the project, added in a few around critical parts that were missing, and before I knew it, I was already up to %80 of my Fable usage.

I guess it should be noted that while this was running, I was also working out some additions to my adversarial-review skill. Having heard some hype around Gemini Flash 3.8, I thought it'd be cool to get its opinions the same way I do Kimi's for plan and code review (and adding Gemini as a reviewer seemed like a good idea). And thus began my antigravity experiment. Initially, my AI friends pointed me towards the Gemini-CLI, but after trying to authenticate, the page directed me towards Antigravity - Google's AI agent harness. After getting it installed and authenticated (I already had a Google AI Pro sub for generating concept art and other POCs), I didn't really have much for it to do, so I continued using Fable in Claude Code to just pass arguments through the command line to get him to do a code review (similar to how I let Kimi do it). 

I wanted to know which of the 2 models the newfound Fable preferred having review its code, so once I got Gemini set up, I told Fable to start having it do code reviews for the unit tests’ changes it was doing alongside Kimi's (this is a standard practice that we do, AI adversarial review after a plan and before a commit). He compared Speed, misses, and the number of problems each exposed. While Gemini worked twice as fast as Kimi and found different code quality bugs, Kimi's slower, more deliberative process won out because her findings saved some real headache. 

So with my Fable usage fast approaching a limit, and a late night + early morning + 9 out of 10 refactor batches still to go, I figured I had done enough Fable token maximization, and it was time to pivot to a more token-efficient workflow. Having not actually used Antigravity or Gemini for code work yet, I thought this was a good opportunity to test it out. I've read online about Fable being less-than-honest about passing work off to lower-model sub-agents and to other AI agents, so I figured I'd just have Gemini implement the next batch, then let Fable and Kimi review its work.

It's only been a night session and a morning session with this workflow for me, but so far I'm loving it! My Fable usage has slowed to a crawl (still have another hour before my weekly reset), Gemini is doing great work implementing everything (the plan is super detailed, so little brainwork for him to do), and kimi is just my slow, constant, deliberative thinker that's always double-checking everyone else's work. It's crazy; it feels like each of my AI assistants is starting to establish a functional, optimized role for the engine (and our work in general). I even went so far as to codify this workflow into a skill for us to use on our other projects (/handoff-round). I'm really looking forward to finding the limit of Fable5.1 as planner, Kimi as a reviewer, and Gemini as the builder (though they all work together on the plan now - it's kind of like a sprint refinement session for them lol)

Anyway, gotta burn this last bit of Fable before my weekly reset in an hour. See you guys around!
-Jesse

P.S. As soon as I go to get Fable to check Gemini’s work 
“API Error: 529 Overloaded. This is a server-side issue, usually 
  temporary — try again in a moment. If it persists, check 
  https://status.claude.com.” 
Such is my life…
