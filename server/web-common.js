export function mathText(target, content) {
  const text = content === undefined ? target : content;
  const root = document.createElement('div'); root.className = 'math-content';
  const raw = String(text || '');
  for (const block of raw.split(/\n\s*\n/)) {
    const heading = /^(#{1,3})\s+(.+)/.exec(block);
    const node = document.createElement(heading ? `h${heading[1].length+1}` : 'p');
    const value = heading ? heading[2] : block;
    let index = 0;
    for (const match of value.matchAll(/\$\$([\s\S]*?)\$\$|\$([^$\n]+)\$/g)) {
      node.append(document.createTextNode(value.slice(index,match.index)));
      const formula = document.createElement('span');
      if (window.katex) {
        try { window.katex.render(match[1] ?? match[2],formula,{displayMode:match[1] !== undefined,throwOnError:true,trust:false,maxExpand:1000}); }
        catch { formula.textContent=match[0]; }
      } else formula.textContent=match[0];
      node.append(formula); index=match.index+match[0].length;
    }
    node.append(document.createTextNode(value.slice(index)));
    root.append(node);
  }
  if (content !== undefined) { target.replaceChildren(root); return target; }
  return root;
}
