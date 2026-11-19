# Excel and CSV message import

Excel (`.xlsx`) is recommended when worksheets and identifier formatting matter. UTF-8 CSV is also supported for a single flat message table. Neither format is sent to the AI as one giant brief: the importer extracts selected message rows, and generation processes each row separately.

## Import messages

1. Open Rewrite and upload or drop an `.xlsx` or `.csv` file. Either upload area opens the spreadsheet preview.
2. Choose one worksheet. Do not select a duplicate message sheet or a project-summary sheet.
3. Confirm the message, language and ID columns. `REPLY_MESSAGE`, `LANGUAGE_FLAG` and `REPLY_ID` are detected automatically. Other names can be mapped without editing the source file.
4. Choose a starting row and press **Preview rows**. Row 1 contains headers; data starts at row 2.
5. Select the messages to process and press **Add messages to bulk**. The importer previews up to the remaining batch capacity.
6. Add writing instructions and select formats as needed. **Keep each spreadsheet row in its original language** uses recognized source-language flags; uncheck it to apply the normal language choices to every row.
7. Generate, review and export the selected copies. Excel exports retain the full generated output in one cell and add original messages, IDs, system codes and workbook/worksheet/row references in separate columns.

For the next batch, remove the previous sources after saving their outputs, upload the workbook again, and select the next starting row. The preview also has **Next rows** to browse another range before importing. Archived generated batches remain available separately.

## Supported structure and limits

- One header row and one message per data row; no merged message cells.
- Unique column headers, up to 80 columns, and up to 100,000 data rows per worksheet.
- `.xlsx` or UTF-8/UTF-16 BOM CSV; CSV may use comma, semicolon or tab separators and quoted multiline cells. Save older `.xls` files as `.xlsx`.
- Upload size at most 10 MB. Very large expanded workbooks are rejected rather than loaded without bounds.
- At most 20 generated output jobs per batch. Selected formats multiply jobs: 5 rows × 4 formats = 20 jobs. One job can contain both output languages.
- Message cells containing formulas are skipped with a note; paste their results as values to import them. Formulas are never executed by the importer.
- Blank message rows are skipped. Duplicate ID/language combinations produce a warning and retain distinct worksheet row identities.
- Source text and placeholders are preserved during import. Zero-padded Excel identifier formats and CSV strings such as `00` are retained. Numeric cells without a zero-padding format cannot reveal zeros already discarded by Excel.
- Language values `en` and `ar`, as well as common English/Arabic names and locale forms, are recognized. Unrecognized or missing flags use the user's selected output languages.
- An optional `EXTRA_INSTRUCTIONS` column supplies row-specific directions. Other operational columns remain tracking metadata and are not sent to the AI as customer copy.
- Excel exports use string cells to prevent formula execution and enforce Excel's 32,767-character cell limit without silently truncating content.

The original workbook is unchanged. Reading and previewing a spreadsheet does not make a generation request. This feature does not launch an unattended 45,000-row processing job: the user explicitly selects each generation batch.
