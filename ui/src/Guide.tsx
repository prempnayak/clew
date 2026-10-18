// The first-visit guide: what Clew is and how to use the war room. Reopen it from the header's "Guide" button.

export function Guide({ onClose, storeUrl }: { onClose: () => void; storeUrl?: string }) {
  return (
    <div className="drawer-bg center-modal" onClick={onClose}>
      <div className="guide" onClick={(e) => e.stopPropagation()}>
        <h2>Welcome to the Clew war room</h2>
        <p className="lead">
          Clew is a team of AI testers. They explore a web store in real browsers and build <b>one shared map</b> of it
          in a graph database (FalkorDB). The map splits the work so no two testers repeat each other, turns every bug
          into exact steps to reproduce it, and is replayed when a new release ships.
        </p>
        <p>
          The store under test is <b>Nebula Gear</b>, a small demo shop with a few planted bugs
          {storeUrl ? (
            <>
              {" "}(<a href={storeUrl} target="_blank" rel="noreferrer">open it</a>)
            </>
          ) : null}
          . The testers don't know where the bugs are.
        </p>

        <div className="steps">
          <div className="step">
            <span className="num">1</span>
            <div>
              <b>Start a session.</b> In <i>Run a test session</i>, keep 4 testers and 10 minutes with a <i>fresh map</i>,
              and press <b>Start</b>.
            </div>
          </div>
          <div className="step">
            <span className="num">2</span>
            <div>
              <b>Watch the map grow.</b> Each circle is a kind of page; arrows are actions. Bigger circles sit on more
              routes and are tested first. <span className="good">Green</span> = fully tested,{" "}
              <span className="amber">amber</span> = work left, a <span className="bad">red ring</span> = a bug was found
              there. Click any page to see its actions.
            </div>
          </div>
          <div className="step">
            <span className="num">3</span>
            <div>
              <b>Follow the bugs</b> (right). A bug is only <i>filed</i> after another tester reproduces it from scratch.
              Click one to see the exact steps, the screenshot and the issue text.
            </div>
          </div>
          <div className="step">
            <span className="num">4</span>
            <div>
              <b>Try a scenario</b> while a session runs:
              <ul>
                <li><b>Kill a tester</b>: its unfinished task is picked up by another tester after its 2-minute lease.</li>
                <li><b>Deploy v2</b>: a new release ships. Every known route is replayed, regressions are filed, renamed
                  buttons are recognised, and fixed bugs are closed. See <i>Release diff</i>.</li>
                <li><b>Continue map</b> (in step 1): a new session reuses the map, so the testers skip straight to work.</li>
              </ul>
            </div>
          </div>
          <div className="step">
            <span className="num">5</span>
            <div>
              <b>Look under the hood.</b> <i>Graph queries</i> shows the Cypher behind every decision: how testers claim work,
              rank pages and find repro steps.
            </div>
          </div>
        </div>
        <p className="muted small-note">
          Clew really clicks and submits forms. It only ever visits this demo store.
        </p>
        <button className="primary" onClick={onClose}>Got it, show me the war room</button>
      </div>
    </div>
  );
}
