/**
 * WBN Instagram bot – betrouwbare klok.
 * GitHub slaat geplande runs vaak over; dit Google Apps Script start de bot elk uur stipt.
 *
 * Eenmalig:
 *  1. Projectinstellingen (tandwiel) → Scripteigenschappen → eigenschap GITHUB_TOKEN = je fine-grained GitHub-token
 *  2. Kies bovenin de functie `setup` en klik op Uitvoeren (geef toestemming als Google erom vraagt)
 */
const REPO = 'finnkops-code/wbn-instagram';
const WORKFLOW = 'instagram.yml';

function runBot() {
  const token = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');
  if (!token) throw new Error('Scripteigenschap GITHUB_TOKEN ontbreekt');
  const res = UrlFetchApp.fetch(
    `https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}/dispatches`,
    {
      method: 'post',
      contentType: 'application/json',
      headers: { Authorization: 'Bearer ' + token, Accept: 'application/vnd.github+json' },
      payload: JSON.stringify({ ref: 'main' }),
      muteHttpExceptions: true,
    }
  );
  if (res.getResponseCode() !== 204) {
    throw new Error(`GitHub gaf ${res.getResponseCode()}: ${res.getContentText()}`);
  }
}

function setup() {
  ScriptApp.getProjectTriggers()
    .filter(t => t.getHandlerFunction() === 'runBot')
    .forEach(t => ScriptApp.deleteTrigger(t));
  ScriptApp.newTrigger('runBot').timeBased().everyHours(1).create();
  runBot(); // meteen testen
}
