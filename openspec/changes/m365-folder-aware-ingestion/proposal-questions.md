# Proposal question round: mailbox plus Excel expected backups

## Answered by user

- Top-level mailbox folders represent customers.
- Some customer folders contain branch/site subfolders.
- Other customer folders contain backup-type subfolders.
- The desired source of expected backups is the mailbox configuration combined
  with the imported Excel configuration.

## Remaining product questions

1. Does the Excel file already contain schedule fields such as weekdays,
   scheduled time, timezone, and report deadline?
2. If the Excel does not contain schedule fields, what default schedule should be
   assumed for imported jobs?
3. When a customer folder contains backup-type subfolders, where should the site
   come from: Excel only, folder name, or a default site?
4. Should folder paths be manually mapped during import preview, or should the app
   infer them from customer/site/technology names?
5. Should the first pilot sync one selected folder at a time, or all configured
   customer folders after import confirmation?
6. Should the app store the source folder path/ID on each inbound message for
   audit and matching explanations?

## Proposed default assumptions

- Excel is the source of truth for customer, site, object, technology, job, and
  schedule fields.
- The mailbox folder path is supporting evidence for routing and matching.
- Folder path never creates a backup result by itself.
- Start with explicit configured folders before recursive discovery.
- Store source folder ID/path as message metadata once folder discovery exists.
