/**
 * Provider Map eligibility — HubSpot custom code workflow action (Node 20).
 *
 * Runs weekly on every customer company. Decides whether the practice is listed on
 * the public "find a provider" map on the brand website.
 *
 *   Device X owners      -> always listed
 *   Device O owners      -> listed only if trailing-365-day consumables >= $5K
 *   Everyone else        -> not listed
 *
 * It writes three flags back to the company so reports and other workflows can reuse them:
 *   has_device_x, has_device_o, consumables_net_last_365, provider_map_eligible
 *
 * The pure function `evaluate()` holds all the logic and is unit-tested in providerMap.test.js.
 * `exports.main` is the thin HubSpot wrapper.
 */

const CONSUMABLES_MIN = 5000;
const DAY_MS = 24 * 60 * 60 * 1000;

/**
 * @param {Array<{product_line: string, amount: number, close_date: string, is_return?: boolean}>} orders
 * @param {Date} today
 */
function evaluate(orders, today = new Date()) {
  const since = new Date(today.getTime() - 365 * DAY_MS);
  let hasX = false;
  let hasO = false;
  let consumables = 0;

  for (const o of orders) {
    const line = (o.product_line || '').toLowerCase();
    if (line === 'device_x') hasX = true;
    if (line === 'device_o') hasO = true;
    if (line === 'consumables' && new Date(o.close_date) >= since) {
      consumables += o.is_return ? -Math.abs(o.amount) : o.amount; // returns net out
    }
  }

  consumables = Math.round(consumables * 100) / 100;
  let eligible = false;
  let reason = 'no qualifying device';
  if (hasX) {
    eligible = true;
    reason = 'owns Device X';
  } else if (hasO && consumables >= CONSUMABLES_MIN) {
    eligible = true;
    reason = `owns Device O and $${consumables.toLocaleString()} consumables in last 365 days`;
  } else if (hasO) {
    reason = `owns Device O but only $${consumables.toLocaleString()} consumables (< $${CONSUMABLES_MIN.toLocaleString()})`;
  }

  return {
    has_device_x: hasX,
    has_device_o: hasO,
    consumables_net_last_365: consumables,
    provider_map_eligible: eligible,
    provider_map_reason: reason,
  };
}

/* ---------------- HubSpot wrapper (not unit-tested; needs a portal) ---------------- */
exports.main = async (event, callback) => {
  const hubspot = require('@hubspot/api-client');
  const client = new hubspot.Client({ accessToken: process.env.PRIVATE_APP_TOKEN });
  const companyId = event.object.objectId;

  // 1. deals associated with the company
  const assoc = await client.crm.associations.v4.basicApi.getPage('companies', companyId, 'deals', undefined, 500);
  const dealIds = assoc.results.map((r) => r.toObjectId);

  // 2. read only closed-won deals with the fields we need
  const orders = [];
  for (let i = 0; i < dealIds.length; i += 100) {
    const batch = await client.crm.deals.batchApi.read({
      inputs: dealIds.slice(i, i + 100).map((id) => ({ id })),
      properties: ['product_line', 'amount', 'closedate', 'dealstage', 'is_return'],
    });
    for (const d of batch.results) {
      if (d.properties.dealstage !== 'closedwon') continue;
      orders.push({
        product_line: d.properties.product_line,
        amount: Number(d.properties.amount || 0),
        close_date: d.properties.closedate,
        is_return: d.properties.is_return === 'true',
      });
    }
  }

  // 3. write the flags back
  const result = evaluate(orders);
  await client.crm.companies.basicApi.update(companyId, {
    properties: {
      has_device_x: String(result.has_device_x),
      has_device_o: String(result.has_device_o),
      consumables_net_last_365: String(result.consumables_net_last_365),
      provider_map_eligible: String(result.provider_map_eligible),
    },
  });

  // outputs can drive the next workflow branch (add to / remove from the map list)
  callback({ outputFields: { provider_map_eligible: result.provider_map_eligible, reason: result.provider_map_reason } });
};

exports.evaluate = evaluate;
exports.CONSUMABLES_MIN = CONSUMABLES_MIN;
