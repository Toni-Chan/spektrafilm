# Profile extensions (sidecars)

Optional per-stock data that only this fork's runtime understands, kept out of
`../profiles/` so that profile JSONs stay loadable by upstream spektrafilm and
by programs that treat every `profiles/*.json` as a film stock (SpektraLab).

Currently: `inhibitor_layers` for Fujifilm's 4th, cyan-sensitive colour layer
(no image dye, inhibits the red layer). `amount_default` is an **estimate**
(see `amount_basis` in each file). Format, model and how forks can use or
ignore these files: `src/spektrafilm_profile_builder/README.md`, section
"Fuji's 4th colour layer". Regenerate with `spektrafilm-profile-builder
extensions` (same README).
