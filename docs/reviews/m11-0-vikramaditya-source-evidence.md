# M11.0 Vikramaditya Source Prerequisite

## Reason

The stopped `m11-0-post-adr` controller assessment found that Issue #132 had
no existing authoritative Vikramaditya scene, shot, or M10 visual-basis
binding. This prerequisite supplies the deterministic source side only; it
does not resume M11.0.

## Exact reconstructable source

| Field | Value |
| --- | --- |
| Source fixture | `tests/fixtures/movie/vikramaditya-opening-story-fragment.json` |
| Project | `vikramaditya-local` |
| Scene | `scene-91f5c8634519d8264e2dd5f8` |
| Selected option | `option-b5d2461f4ec95dc0377938ba` (`location_live_action`) |
| Selected shot | `shot-024b0d6352149eabb74df543` (`primary_action`) |
| Selected shot-card digest | `8dd0e25e170f90776b406ffafea95f5e10179bd131072cf79ecb283bd1a3635b` |
| Corresponding storyboard frame | `frame-fb0d79ba59d7781b0bad3e7e` |
| Frame specification digest | `4ff516866b0123661613c2d47aec059ee802822fcf22776314cca7a1ad5f12d6` |
| Storyboard specification digest | `e5f9a09e9bb0744d9587975fa40012483dbf94d370aa7e639cc0285ce4c5f75c` |

Reconstruct the source artifacts through the real path:

```text
vss movie demo --story tests/fixtures/movie/vikramaditya-opening-story-fragment.json --reviewer-id source.preparation --option-id option-b5d2461f4ec95dc0377938ba --correlation-id vikramaditya-source --storyboard-specification
```

The source fixture is `public`, `approved_fixture`, `original`, and
`legendary`; those declarations remain source claims rather than rights or
cultural authority. The end-to-end reconstruction and substitution rejection
are tested in `tests/movie_storyboard/test_m11_0_vikramaditya_source.py`.

## M10 visual-basis status

Candidate 1 remains preserved as rejected audit evidence: its request is bound to
the superseded `minimal_stage` option and it must not be promoted, compared, or
reused as the M11.0 visual basis.

No M10 visual-basis logical asset, revision, content digest, catalogue entry,
or shot binding exists yet. The existing M10 route can create one only after
the explicit human paid-provider gate: it requires controlled external
candidate generation, human review/selection/promotion, and M10.4 admission
before M10.5/6 can register and bind the resulting asset. This prerequisite
does not invoke or authorize that work. M11.0 remains stopped until such an
admitted binding is produced and this record is updated with its exact
`asset_id`, revision, asset digest, admission digest, and binding digest.
