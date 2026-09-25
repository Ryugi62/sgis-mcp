# 라이브 검증 기록 — 2026-09-25 19:30 KST

> 실제 SGIS OpenAPI 호출(sgisapi.mods.go.kr). trId는 SGIS 쪽 거래번호다.

도구 12개 중 성공 12개

| # | 도구 | 결과 | trId |
|---|---|---|---|
| 1 | `sgis_data_years` | ✅ 최신 census 2024, company 2024, agriculture 2020, boundary 2025, small_area_boundary 2025 | `C87w_API_9902_1790332210527` |
| 2 | `sgis_find_region` | ✅ 경상남도 창원시 의창구 → 38111 | `hGu7_API_0701_1790332210643, zUdM_API_0701_1790332211261` |
| 3 | `sgis_population_summary` | ✅ 7행 · 기준연도 2024 | `dMCh_API_0301_1790332211380` |
| 4 | `sgis_population_by_age` | ✅ 7행 · 기준연도 2024 | `Pe3*_API_0312_1790332211487`<br>`dMCh_API_0301_1790332211380` |
| 5 | `sgis_households` | ✅ 7행 · 기준연도 2024 | `iGOH_API_0305_1790332212136` |
| 6 | `sgis_houses` | ✅ 7행 · 기준연도 2024 | `00Mk_API_0306_1790332212266` |
| 7 | `sgis_industry_codes` | ✅ 21개 코드 · 11차 | `rIKE_API_0303_1790332212399` |
| 8 | `sgis_companies` | ✅ 22행 · 기준연도 2024 | `RGGS_API_0304_1790332213017` |
| 9 | `sgis_geocode` | ✅ 경상남도 창원시의창구 봉림동 (창원대학로 20) → (128.68712478565752, 35.248214215376024) | `HalH_API_0707_1790332213153` |
| 10 | `sgis_reverse_geocode` | ✅ 1건 | `p0bo_API_0708_1790332213286` |
| 11 | `sgis_transform_coord` | ✅ (1108001.5647409316, 1695400.3895694548) EPSG:5179 | `XYXS_API_0201_1790332213427` |
| 12 | `sgis_choropleth` | ✅ 경상남도 창원시 의창구 65세이상 인구 비율 (2024년) · 7개 지역 → sgis_38111_age_share_24_2024.svg | `dMCh_API_0301_1790332211380`<br>`Pe3*_API_0312_1790332211487`<br>`augP_API_0704_1790332214045` |
