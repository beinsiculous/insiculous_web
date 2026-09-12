// Parser and pure rules for Playwright's ariaSnapshot trees.
//
// Screen readers walk the accessibility tree rather than the DOM. This module parses
// Playwright's YAML-like text snapshot into a list of nodes and checks the structural invariants:
// landmarks, a single h1 with no skipped heading levels, named interactive controls, and named
// regions and dialogs.

/**
 * Parse Playwright's ariaSnapshot YAML-like text format into an array of nodes.
 *
 * Each node has { depth, role, name, attributes }.
 * Lines starting with /url or text are ignored by name.
 * Continuation lines fold into the previous node's name or are ignored following an ignored line.
 */
export function parseAriaSnapshot(text) {
  const lines = text.split("\n");
  const nodes = [];
  let lastDisposition = null; // "node" | "ignored"
  let waitingForQuoteClose = false;

  for (let lineNumber = 0; lineNumber < lines.length; lineNumber += 1) {
    const rawLine = lines[lineNumber];
    if (!rawLine.trim()) {
      continue;
    }

    const indentMatch = rawLine.match(/^(\s*)(.*)$/);
    const leadingSpaces = indentMatch[1].length;
    const content = indentMatch[2];

    if (!content.startsWith("- ")) {
      // Continuation line (wrapped text)
      if (lastDisposition === "ignored") {
        continue;
      }
      if (lastDisposition === "node" && nodes.length > 0) {
        const lastNode = nodes[nodes.length - 1];
        const trimmed = content.trim();
        if (waitingForQuoteClose) {
          const closeMatch = trimmed.match(/^(.*?)"((?:\s+\[[^\]]+\])*)(?:\s*:\s*(.*)|\s*)?$/);
          if (closeMatch) {
            const addedText = closeMatch[1].replace(/\\([\\"])/g, "$1");
            lastNode.name = lastNode.name ? `${lastNode.name} ${addedText}` : addedText;
            if (closeMatch[2]) {
              for (const attrMatch of closeMatch[2].matchAll(/\[([a-zA-Z0-9_-]+)(?:=([^\]]*))?\]/g)) {
                const key = attrMatch[1];
                const attributeValue = attrMatch[2];
                lastNode.attributes[key] = attributeValue === undefined ? true : (/^\d+$/.test(attributeValue) ? parseInt(attributeValue, 10) : attributeValue);
              }
            }
            waitingForQuoteClose = false;
          } else {
            const addedText = trimmed.replace(/\\([\\"])/g, "$1");
            lastNode.name = lastNode.name ? `${lastNode.name} ${addedText}` : addedText;
          }
        } else {
          lastNode.name = lastNode.name ? `${lastNode.name} ${trimmed}` : trimmed;
        }
        continue;
      }
      throw new Error(
        `Unrecognized ariaSnapshot line ${lineNumber + 1}: "${rawLine}". ` +
        `This may indicate Playwright changed its format or page text has an unexpected shape.`
      );
    }

    const depth = leadingSpaces / 2;
    let item = content.slice(2).trim();

    // Property lines under a node are not nodes and carry no name of their own. Playwright
    // writes every element property it reports this way — `/url: /games/` on a link,
    // `/placeholder: …` on a textbox — so the match is on the slash, not on a list of
    // property names: the list was `/url` alone until the playground's script editor put a
    // placeholder on the page and the gate threw on it. Free text lines are ignored the same
    // way.
    if (/^\/[a-z][a-z0-9_-]*(?::\s*.*)?$/.test(item) || /^text(?::\s*.*)?$/.test(item)) {
      lastDisposition = "ignored";
      waitingForQuoteClose = false;
      continue;
    }

    // Strip single-quoted key if present: '- \'role "name" [attrs]\':'
    if (item.startsWith("'")) {
      const quotedKeyMatch = item.match(/^'((?:[^']|'')*)'(.*)$/);
      if (!quotedKeyMatch) {
        throw new Error(
          `Unrecognized ariaSnapshot line ${lineNumber + 1}: "${rawLine}". ` +
          `This may indicate Playwright changed its format or page text has an unexpected shape.`
        );
      }
      const unescapedKey = quotedKeyMatch[1].replace(/''/g, "'");
      item = (unescapedKey + quotedKeyMatch[2]).trim();
    }

    // Standard shape:
    // role [optional "name"] [optional [attr] / [attr=value] ...] [optional : or : text]
    const nodeMatch = item.match(
      /^([a-z][a-z0-9_-]*)(?:\s+"((?:[^"\\]|\\.)*)")?((?:\s+\[[^\]]+\])*)(?:\s*:\s*(.*)|\s*)?$/
    );

    if (nodeMatch) {
      const role = nodeMatch[1];
      const rawName = nodeMatch[2];
      const rawAttrs = nodeMatch[3];

      const name = rawName !== undefined ? rawName.replace(/\\([\\"])/g, "$1") : "";
      const attributes = {};
      if (rawAttrs) {
        for (const attrMatch of rawAttrs.matchAll(/\[([a-zA-Z0-9_-]+)(?:=([^\]]*))?\]/g)) {
          const key = attrMatch[1];
          const attributeValue = attrMatch[2];
          if (attributeValue === undefined) {
            attributes[key] = true;
          } else if (/^\d+$/.test(attributeValue)) {
            attributes[key] = parseInt(attributeValue, 10);
          } else {
            attributes[key] = attributeValue;
          }
        }
      }

      nodes.push({ depth, role, name, attributes });
      lastDisposition = "node";
      waitingForQuoteClose = false;
      continue;
    }

    // Check for an opening quote that wraps to a continuation line: - role "start of name
    const unclosedMatch = item.match(/^([a-z][a-z0-9_-]*)\s+"(.*)$/);
    if (unclosedMatch) {
      const role = unclosedMatch[1];
      const rawName = unclosedMatch[2];
      const name = rawName.replace(/\\([\\"])/g, "$1");
      nodes.push({ depth, role, name, attributes: {} });
      lastDisposition = "node";
      waitingForQuoteClose = true;
      continue;
    }

    throw new Error(
      `Unrecognized ariaSnapshot line ${lineNumber + 1}: "${rawLine}". ` +
      `This may indicate Playwright changed its format or page text has an unexpected shape.`
    );
  }

  return nodes;
}

const CONTROL_ROLES = new Set([
  "link",
  "button",
  "textbox",
  "combobox",
  "checkbox",
  "radio",
  "slider",
  "switch",
  "tab",
  "menuitem",
]);

/**
 * Universal accessibility findings for one page tree.
 *
 * Rules:
 * 1. landmarks: exactly one main, at least one navigation, a banner and a contentinfo.
 * 2. headings: exactly one level-1 heading, it comes first, and going down the page no level is skipped.
 * 3. control names: every link, button, textbox, combobox, checkbox, radio, slider, switch, tab, menuitem has a name.
 * 4. named regions and dialogs: every region and dialog node has a name.
 *
 * Returns an array of human-readable failure descriptions (empty if compliant).
 */
export function announceFindings(nodes) {
  const findings = [];

  // 1. Landmarks
  const mainNodes = nodes.filter((node) => node.role === "main");
  if (mainNodes.length !== 1) {
    findings.push(`landmarks: expected exactly one main landmark, found ${mainNodes.length}`);
  }

  const navNodes = nodes.filter((node) => node.role === "navigation");
  if (navNodes.length === 0) {
    findings.push("landmarks: missing navigation landmark");
  }

  const bannerNodes = nodes.filter((node) => node.role === "banner");
  if (bannerNodes.length === 0) {
    findings.push("landmarks: missing banner landmark");
  }

  const contentinfoNodes = nodes.filter((node) => node.role === "contentinfo");
  if (contentinfoNodes.length === 0) {
    findings.push("landmarks: missing contentinfo landmark");
  }

  // 2. Headings
  const headingNodes = nodes.filter((node) => node.role === "heading");
  const h1Nodes = headingNodes.filter((node) => node.attributes.level === 1);
  if (h1Nodes.length !== 1) {
    findings.push(`headings: expected exactly one level-1 heading, found ${h1Nodes.length}`);
  }

  if (headingNodes.length > 0 && headingNodes[0].attributes.level !== 1) {
    findings.push(
      `headings: first heading must be level 1, found level ${headingNodes[0].attributes.level} ("${headingNodes[0].name}")`
    );
  }

  let previousLevel = null;
  for (const heading of headingNodes) {
    const currentLevel = heading.attributes.level;
    if (typeof currentLevel !== "number") {
      findings.push(`headings: heading "${heading.name}" has no level attribute`);
      continue;
    }
    if (previousLevel !== null && currentLevel > previousLevel + 1) {
      findings.push(
        `headings: skipped level ${currentLevel} ("${heading.name}") follows level ${previousLevel}`
      );
    }
    previousLevel = currentLevel;
  }

  // 3. Control names
  for (const node of nodes) {
    if (CONTROL_ROLES.has(node.role)) {
      if (!node.name || !node.name.trim()) {
        findings.push(`control names: bare role "${node.role}" has no accessible name`);
      }
    }
  }

  // 4. Named regions and dialogs (group nodes are exempt by design)
  for (const node of nodes) {
    if (node.role === "region" || node.role === "dialog") {
      if (!node.name || !node.name.trim()) {
        findings.push(`named regions and dialogs: "${node.role}" has no accessible name`);
      }
    }
  }

  return findings;
}

/**
 * Check seeded sentinels: returns list of expected heading names not present in the nodes.
 */
export function missingSentinels(route, nodes, sentinels) {
  const expectedHeadings =
    (sentinels instanceof Map ? sentinels.get(route) : sentinels?.[route]) ?? [];
  if (!expectedHeadings || expectedHeadings.length === 0) {
    return [];
  }
  const headingNames = new Set(
    nodes.filter((node) => node.role === "heading").map((node) => node.name)
  );
  return expectedHeadings.filter((expected) => !headingNames.has(expected));
}
