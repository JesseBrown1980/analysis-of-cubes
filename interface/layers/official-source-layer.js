const PR038 = Object.freeze({
  caseId: 'PR-038',
  command: 'USCENTCOM',
  eventYear: '2013',
  status: 'UNRESOLVED',
  duration: '00:01:46',
  officialAsset: 'DOD_111689051',
  officialVideoId: 'DVIDS 1006088',
  reportedMasterSha256: 'BD3F5269C3F123B90DB76C9496F8DDBB145184C66B0C11CD3CFD9E54F5B683B6',
  masterVerification: 'REPORTED_REMOTE',
  controlAsset: 'OE9_mAcvCT8',
  controlClass: 'THIRD_PARTY_RECODE',
  narrativeAuthority: 'INFORMATIONAL_ONLY_NOT_ANALYTICAL_JUDGMENT'
});

const style = document.createElement('style');
style.textContent = `
  .source-authority {
    display: none;
    margin-top: 10px;
    padding-top: 9px;
    border-top: 1px solid rgba(var(--immersion-accent-rgb), .13);
  }
  body[data-immersion-layer="shell12"] .source-authority,
  body[data-immersion-layer="evidence"] .source-authority { display: block; }
  .source-authority header {
    display: flex;
    justify-content: space-between;
    color: #6f8e88;
    font: 7px/1 "Cascadia Mono", Consolas, monospace;
    letter-spacing: .13em;
  }
  .source-authority header b { color: var(--immersion-accent); font-weight: 500; }
  .source-lanes { display: grid; gap: 4px; margin-top: 7px; }
  .source-lane {
    display: grid;
    grid-template-columns: 54px 1fr auto;
    align-items: center;
    gap: 7px;
    padding: 6px 7px;
    background: rgba(var(--immersion-accent-rgb), .035);
    border-left: 2px solid rgba(var(--immersion-accent-rgb), .28);
  }
  .source-lane small,
  .source-lane code,
  .source-lane b {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font: 7px/1 "Cascadia Mono", Consolas, monospace;
  }
  .source-lane small { color: #68837d; letter-spacing: .1em; }
  .source-lane code { color: #b7cbc6; }
  .source-lane b { color: var(--immersion-accent); font-weight: 500; }
  .source-lane.control b { color: #8fa49f; }
  .source-boundary {
    margin: 7px 0 0;
    color: #78918c;
    font: 7px/1.4 "Cascadia Mono", Consolas, monospace;
    letter-spacing: .05em;
  }
  .source-sha {
    display: block;
    margin-top: 6px;
    overflow: hidden;
    text-overflow: ellipsis;
    color: #708b85;
    font: 7px/1 "Cascadia Mono", Consolas, monospace;
    white-space: nowrap;
  }
`;
document.head.append(style);

function attachAuthorityPanel() {
  const consolePanel = document.querySelector('.immersion-console');
  if (!consolePanel) {
    setTimeout(attachAuthorityPanel, 25);
    return;
  }

  const panel = document.createElement('section');
  panel.className = 'source-authority';
  panel.innerHTML = `
    <header><span>AUTORIDADE DA FONTE</span><b>${PR038.caseId} · ${PR038.status}</b></header>
    <div class="source-lanes">
      <div class="source-lane">
        <small>MASTER</small>
        <code>${PR038.officialAsset} · ${PR038.duration}</code>
        <b>DVIDS</b>
      </div>
      <div class="source-lane">
        <small>CASO</small>
        <code>${PR038.command} · ${PR038.eventYear}</code>
        <b>AARO</b>
      </div>
      <div class="source-lane control">
        <small>CONTROLE</small>
        <code>${PR038.controlAsset}</code>
        <b>RECODE</b>
      </div>
    </div>
    <p class="source-boundary">A descrição visual oficial é informativa e não representa julgamento analítico, conclusão investigativa ou determinação factual.</p>
    <code class="source-sha" title="${PR038.reportedMasterSha256}">SHA MASTER · ${PR038.reportedMasterSha256} · ${PR038.masterVerification}</code>`;
  consolePanel.append(panel);
}

attachAuthorityPanel();
