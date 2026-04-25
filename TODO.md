# Fix Invoice PDF Template Configuration Display

- [x] 1. Read and understand `app/pdf_templates/invoice_template.py` and `app/pdf_utils.py`
- [x] 2. Confirm plan with user
- [x] 3. Update `_apply_template_settings()` in `app/pdf_utils.py` to load `SHOW_*` and `FOOTER_SHOW_*` flags
- [x] 4. Update `_build_bottom_section()` in `app/pdf_utils.py` to respect show/hide flags for bank details, terms, and notes
- [x] 5. Update `_draw_footer()` in `app/pdf_utils.py` to render `FOOTER_MESSAGE` and conditionally show page number / company info
- [x] 6. Verify no syntax errors and test PDF generation

