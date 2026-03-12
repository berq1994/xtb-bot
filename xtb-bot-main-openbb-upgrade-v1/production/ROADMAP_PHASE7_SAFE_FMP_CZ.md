# Phase 7 Safe FMP hotfix

Tento hotfix mění FMP integraci na best-effort režim.

## Co dělá
- při FMP 402 Payment Required nepřeruší celý běh
- tracker a Telegram pokračují dál
- autofill může být 0 bez pádu pipeline

## Další krok
- upravit endpointy podle skutečně dostupného FMP plánu nebo přepnout provider
