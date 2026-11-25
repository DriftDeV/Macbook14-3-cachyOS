-- macbook-manager-audio.lua: riapplica al filtro "MacBook Pro 14,3 Speakers" (pkgs/mbp143-audio) le impostazioni
-- audio scelte in MacBook Manager (scheda Audio), ogni volta che il filtro nasce: avvio, riavvio di WirePlumber,
-- cuffie scollegate (il profilo torna a 4 canali e il grafo viene ricreato), nuovo accesso.
--
-- Le impostazioni sono nel file di stato ~/.local/state/wireplumber/macbook-manager-audio, scritto dal manager.
-- Solo i controlli elencati qui sotto, ognuno limitato: i guadagni f6 non superano il valore di fabbrica e
-- limitatori, protezione termica e BuzzKill non sono tra i controlli raggiungibili.
-- Installato da scripts/install-manager.sh come /usr/local/share/wireplumber/scripts/macbook-manager/audio-settings.lua.

log = Log.open_topic ("s-macbook-manager-audio")

local NODE = "audio_effect.mbp143-speakers"
local F6_FACTORY = 1.188502
local LIMITS = {
  ["bassex:bypass"] = { 0, 1 },
  ["bassex:amt"] = { 0.5, 2.5 },
  ["bassex:ceil"] = { 100, 250 },
  ["bassex:final_hp"] = { 100, 250 },
  ["bassex:blend"] = { 0, 1 },
  ["bassex:sat_second"] = { 0, 3 },
  ["bassex:sat_third"] = { 0, 3 },
  -- livello minimo: -12 dB di livello e -12 dB di bilanciamento insieme (x 0,0625); massimo: la fabbrica
  ["f6c0gain:Mult"] = { F6_FACTORY * 0.0625, F6_FACTORY },
  ["f6c1gain:Mult"] = { F6_FACTORY * 0.0625, F6_FACTORY },
  ["f2loudness:bypass"] = { 0, 1 },
  ["f1mozartCompressor:bypass"] = { 0, 1 },
  ["f4mozartCompressorDualBand:bypass"] = { 0, 1 },
}

function apply (node)
  local saved = State ("macbook-manager-audio"):load ()
  local params = {}
  for key, lim in pairs (LIMITS) do
    local v = tonumber (saved [key] or "")
    if v ~= nil then
      v = math.max (lim [1], math.min (lim [2], v)) * 1.0
      table.insert (params, key)
      table.insert (params, v)
    end
  end
  if #params == 0 then
    return
  end
  log:info (node, string.format ("applying %d saved controls", #params // 2))
  node:set_param ("Props", Pod.Object {
    "Spa:Pod:Object:Param:Props", "Props",
    params = Pod.Struct (params),
  })
end

om = ObjectManager {
  Interest {
    type = "node",
    Constraint { "node.name", "equals", NODE, type = "pw-global" },
  }
}

om:connect ("object-added", function (_, node)
  apply (node)
end)

om:activate ()
