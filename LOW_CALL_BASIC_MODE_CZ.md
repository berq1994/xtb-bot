# Low-call Basic režim pro FMP

Tato verze je upravená pro FMP Basic plán.

Co se změnilo:
- autonomous-core už nespouští FMP smoke test při každém běhu
- market overview v low-call režimu preferuje yfinance a FMP používá jen jako nouzový EOD doplněk
- FMP news jsou v autonomous-core vypnuté, aby se neplýtvalo limitem
- outcome tracking v low-call režimu preferuje yfinance
- FMP má lokální denní rozpočet a cache v `.state/`

Doporučené workflow:
- průběžně: `autonomous-core`
- ručně po změně klíče nebo pro kontrolu: `fmp-smoke-test`

Co čekat v logu:
- `Zdroj dat: yfinance_low_call` nebo `openbb_low_call`
- méně nebo žádné 429 v autonomous-core
- FMP se má šetřit hlavně na EOD/historická data
