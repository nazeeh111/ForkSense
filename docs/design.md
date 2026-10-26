# A record from the workbench

ForkSense uses the visual language of a laboratory notebook and a signal diagram: warm paper, dark graphite, oxide red for experimental forks, and green for observed evidence. The fork symbol begins with one observation and separates into two alternatives. It makes no claim about a search algorithm or hidden agent reasoning.

The single-file report works offline. A compact worktree map shows the frozen base and its actual probe and repair children. A recorded repair verifier is a child of that repair, labeled as a fresh base with the candidate patch. The map is an execution topology, separate from evidence chronology; it does not imply that a repair continues a probe snapshot. Native node buttons open and focus the corresponding evidence, including when a filter had hidden it. Execution occupies the main column. Each experiment opens to reveal its real command, output, policy score and independent verification. A checkpoint selector shows how the supplied hypothesis weights changed. Failed or inconclusive results stay visible. A candidate panel presents patch identity and verification separately, and never invokes acceptance from the browser.

System sans-serif text and system monospace text keep the report small and independent of fonts or third-party assets. Native `details`, `summary`, `select` and `button` controls preserve keyboard operation. Focus rings, explicit text states, mobile stacking and no decorative motion support inspection across devices. Logs are escaped text; report JSON escapes script terminators before embedding.

Brand assets are original SVG source created for this project. `engine-flow.svg` describes external bounded execution and protected verification. `hero.svg` and `wordmark.svg` are presentation assets, not screenshots or benchmark evidence.

## Report verification

The current report renderer was exercised in local Chrome at 1440 px and 390 px using explicitly labeled UI fixtures. Both layouts had no horizontal overflow or page errors. Native Enter activation expanded the experiment steps, filtering selected repairs, checkpoint selection changed the displayed posterior weights, and embedded script-like content remained text. The first Tab exposed the skip link with a visible outline. These checks establish report behavior, not benchmark results or agent success. Public screenshots should be captured from an actual recorded run.
