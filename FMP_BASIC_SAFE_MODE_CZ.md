# FMP basic safe mode

Tato verze přepíná FMP použití do bezpečnějšího režimu pro základní plán:

- smoke test už nehodnotí jen quote endpoint
- přidán je test EOD endpointu `historical-price-eod/light`
- market overview bere u FMP primárně EOD data místo live quote
- když quote endpoint neprojde, bot se může opřít o poslední EOD close
- v přehledech se zdroj zobrazuje jako `FMP (EOD safe mode)`

Doporučený test po nahrání:

1. `fmp-smoke-test`
2. `autonomous-core`
3. `email-morning`

V logu hledej hlavně:

- `TEST FMP SAFE MODE (EOD)`
- `Verdikt: FMP SAFE MODE AKTIVNÍ`
- `Zdroj dat: fmp_eod`
