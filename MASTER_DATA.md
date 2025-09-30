# logo_master 마스터 데이터 쿼리

## 필드 설명
- **infomax_code**: 종목 고유 식별자
- **crawling_ticker**: 크롤링할 때 조회할 URL에 넣을 티커
- **fs_entity_name**: 기업코드
- **api_domain**: API로 확인할 웹사이트 주소
- **sprovider**: 운용사코드
- **logo_hash**: `md5(COALESCE(sprovider, fs_entity_id::text, infomax_code::text))`

## 기존 API 연동
- **API 엔드포인트**: `http://10.150.2.150:8004/api/schemas/raw_data/tables/logo_master/query`
- **응답 구조**: `{"schema": "raw_data", "table": "logo_master", "data": [...], "columns": [...]}`
- **쿼리 파라미터**: `limit`, `infomax_code`, `fs_regional_id`, `fs_entity_id` 등

## 샘플 데이터
```
infomax_code,crawling_ticker,fs_entity_name,api_domain,sprovider,logo_hash
AMX:AAA,AMEX-AAA,INVESTMENT MANAGERS SERIES TR II ALTERNATIVE ACCESS FIRST PR,,US0225,8485b1610697af8af71a8d8163c225e7
AMX:AAAA,AMEX-AAAA,AMPLIUS AGGRESSIVE ASSET ALLOCATION ETF,,US0557,68bd3a90c020c9656111bec4ab92ed03
AMX:AAAU,AMEX-AAAU,GOLDMAN SACHS PHYSICAL GOLD ETF UNIT,,US0086,85666ce04c4122e26bd12eec4b17e46d
```

## Materialized View 생성 쿼리
```sql
CREATE MATERIALIZED VIEW logo_master AS
WITH base_data AS (
    SELECT a.infomax_code,
           a.isin,
           a.fs_exchange,
           a.fs_regional_id,
           a.english_name,
           a.fs_entity_id,
           a.fs_entity_name,
           a.iso_mic,
           a.fs_ticker,
           split_part(a.infomax_code::text, ':'::text, 1) AS gts_exchange,
           split_part(a.infomax_code::text, ':'::text, 2) AS gts_ticker
    FROM raw_data.infomax_factset_master a
    WHERE a.infomax_code IS NOT NULL
),
enriched_data AS (
    SELECT b.infomax_code,
           b.isin,
           b.fs_exchange,
           b.fs_regional_id,
           b.english_name,
           b.fs_entity_id,
           b.fs_entity_name,
           b.iso_mic,
           b.fs_ticker,
           b.gts_exchange,
           b.gts_ticker,
           c."인포맥스코드" AS terminal_code,
           split_part(c."인포맥스코드", ':'::text, 1) AS terminal_exchange,
           split_part(c."인포맥스코드", ':'::text, 2) AS terminal_ticker,
           d.web_site,
           f.sprovider,
           row_number() OVER (PARTITION BY b.infomax_code ORDER BY b.fs_exchange DESC NULLS LAST) AS rn
    FROM base_data b
    LEFT JOIN raw_data."인포맥스종목마스터" c
        ON b.gts_exchange = c.gts_exnm AND b.gts_ticker = c."gts_티커"
    LEFT JOIN raw_data.ent_v1_ent_entity_coverage d
        ON b.fs_entity_id::text = d.factset_entity_id::text
    LEFT JOIN raw_data.fe1000tb_kor f 
        ON b.isin::text = f.sisin 
        AND f.scode = c."인포맥스코드" 
        AND f.susetype = 'Y'::text 
        AND f.sprovider IS NOT NULL 
        AND f.sprovider <> 'NA'::text
),
final_data AS (
    SELECT enriched_data.infomax_code,
           enriched_data.isin,
           enriched_data.fs_exchange,
           enriched_data.fs_regional_id,
           enriched_data.english_name,
           enriched_data.fs_entity_id,
           enriched_data.fs_entity_name,
           enriched_data.iso_mic,
           enriched_data.fs_ticker,
           enriched_data.gts_exchange,
           enriched_data.gts_ticker,
           enriched_data.terminal_code,
           enriched_data.terminal_exchange,
           enriched_data.terminal_ticker,
           enriched_data.web_site,
           enriched_data.sprovider,
           enriched_data.rn
    FROM enriched_data
    WHERE enriched_data.rn = 1
),
processed_data AS (
    SELECT final_data.infomax_code,
           final_data.isin,
           final_data.fs_exchange,
           final_data.fs_regional_id,
           final_data.english_name,
           final_data.fs_entity_id,
           final_data.fs_entity_name,
           final_data.iso_mic,
           final_data.fs_ticker,
           final_data.gts_exchange,
           final_data.gts_ticker,
           final_data.terminal_code,
           final_data.terminal_exchange,
           final_data.terminal_ticker,
           final_data.web_site,
           final_data.sprovider,
           final_data.rn,
           replace(final_data.infomax_code::text, ':'::text, '_'::text) AS infomax_code_export_name,
           replace(final_data.terminal_code, ':'::text, '_'::text) AS terminal_code_export_name,
           CASE
               WHEN final_data.web_site IS NULL OR TRIM(BOTH FROM final_data.web_site) = ''::text
                   THEN NULL::text
               ELSE TRIM(BOTH FROM regexp_replace(split_part(regexp_replace(regexp_replace(
                                                                                lower(TRIM(BOTH FROM final_data.web_site)),
                                                                                '^[a-z]+://'::text,
                                                                                ''::text),
                                                                        '^www\.'::text,
                                                                        ''::text), '/'::text,
                                                         1), ':[0-9]+$'::text, ''::text))
               END AS api_domain,
           md5(COALESCE(final_data.sprovider, final_data.fs_entity_id::text,
                        final_data.infomax_code::text)) AS logo_hash
    FROM final_data
)
SELECT infomax_code,
       terminal_code,
       infomax_code_export_name,
       terminal_code_export_name,
       CASE
           WHEN gts_exchange = 'NAS'::text THEN 'NASDAQ-'::text || terminal_ticker
           WHEN gts_exchange = 'NYS'::text THEN
               CASE
                   WHEN terminal_ticker ~~ '%.UN'::text
                       THEN 'NYSE-'::text || replace(terminal_ticker, '.UN'::text, '.U'::text)
                   ELSE 'NYSE-'::text || regexp_replace(terminal_ticker, '\.'::text, '/P\1'::text)
                   END
           WHEN gts_exchange = 'TSE'::text THEN 'TSE-'::text || terminal_ticker
           WHEN gts_exchange = 'LNS'::text THEN 'LSE-'::text || terminal_ticker
           WHEN gts_exchange = 'HKS'::text THEN 'HKEX-'::text || ltrim(terminal_ticker, '0'::text)
           WHEN gts_exchange = 'TSX'::text THEN 'TSX-'::text || terminal_ticker
           WHEN gts_exchange = 'SGS'::text THEN 'SGX-'::text || terminal_ticker
           WHEN gts_exchange = 'SHS'::text THEN 'SSE-'::text || terminal_ticker
           WHEN gts_exchange = 'SZS'::text THEN 'SZSE-'::text || terminal_ticker
           WHEN gts_exchange = 'TWS'::text THEN 'TWSE-'::text || terminal_ticker
           WHEN gts_exchange = 'TPE'::text THEN 'TPEX-'::text || terminal_ticker
           WHEN gts_exchange = 'XET'::text THEN 'XETR-'::text || terminal_ticker
           WHEN gts_exchange = 'HSX'::text THEN 'HOSE-'::text || terminal_ticker
           WHEN gts_exchange = 'HNX'::text THEN 'HNX-'::text || terminal_ticker
           WHEN gts_exchange = 'IDX'::text THEN 'IDX-'::text || terminal_ticker
           WHEN gts_exchange = 'EUN'::text THEN 'EURONEXT-'::text || replace(terminal_ticker, '.'::text, '-'::text)
           WHEN gts_exchange = 'AMX'::text THEN
               CASE
                   WHEN terminal_ticker ~~ '%.UN'::text
                       THEN 'AMEX-'::text || replace(terminal_ticker, '.UN'::text, '.U'::text)
                   ELSE 'AMEX-'::text || regexp_replace(terminal_ticker, '\.'::text, '/P\1'::text)
                   END
           ELSE NULL::text
           END AS crawling_ticker,
       isin,
       gts_exchange,
       fs_exchange,
       terminal_exchange,
       iso_mic,
       gts_ticker,
       terminal_ticker,
       fs_ticker,
       fs_regional_id,
       english_name,
       fs_entity_id,
       fs_entity_name,
       api_domain,
       sprovider,
       logo_hash
FROM processed_data
WHERE infomax_code IS NOT NULL
ORDER BY gts_exchange, terminal_ticker;
```

## 사용 용도
- **크롤러 입력**: `crawling_ticker`로 TradingView URL 생성
- **logo.dev API**: `api_domain`으로 API 호출
- **중복 체크**: `logo_hash`로 중복 방지
- **데이터 매핑**: `infomax_code`로 로고와 종목 연결