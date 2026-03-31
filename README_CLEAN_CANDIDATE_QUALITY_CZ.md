# Clean Candidate Quality Fix

Tento patch posouvá systém z fáze "vše noisy" do fáze, kdy umí rozlišit lepší long kandidáty jako **clean**.

## Co se mění
- Zavádí se `clean_long_score`
- Silné kombinace trend + momentum + TA + fundamenty + official support se mohou dostat do `clean`
- Learning vrstva nepoužívá pouze news evidence grade, ale i širší kontext signálu
- Nové signály si ukládají více kontextu do historie

## Co po nahrání vyzkoušet
1. autonomous-core
2. learning-review
3. weekly-review

## Na co se dívat
- zda v `learning-review` naskočí první `Čisté vzorky`
- zda se `buy_candidate` rozdělí na `clean` a `noisy`
- zda weekly review přestane psát, že nejsou žádní kandidáti po kvalitativním filtru
