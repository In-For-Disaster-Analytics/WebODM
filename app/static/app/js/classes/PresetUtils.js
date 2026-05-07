import Utils from './Utils';
import { _, interpolate } from './gettext';

class PresetUtils{
  static getCategoricalOverrides(){
    return {
      "camera-lens": ["auto", "perspective", "brown", "fisheye", "spherical", "equirectangular", "dual"],
      "end-with": ["dataset", "split", "merge", "opensfm", "openmvs", "odm_filterpoints", "odm_meshing", "mvs_texturing", "odm_georeferencing", "odm_dem", "odm_orthophoto", "odm_report", "odm_postprocess"],
      "feature-quality": ["ultra", "high", "medium", "low", "lowest"],
      "feature-type": ["akaze", "hahog", "orb", "sift"],
      "matcher-type": ["bow", "bruteforce", "flann"],
      "merge": ["all", "pointcloud", "orthophoto", "dem"],
      "orthophoto-compression": ["JPEG", "LZW", "PACKBITS", "DEFLATE", "LZMA", "NONE"],
      "pc-quality": ["ultra", "high", "medium", "low", "lowest"],
      "radiometric-calibration": ["none", "camera", "camera+sun"],
      "sfm-algorithm": ["incremental", "triangulation", "planar"]
    };
  }

  static parseDomainFromString(domain){
    if (typeof domain !== "string") return null;
    const trimmed = domain.trim();
    if (!trimmed) return null;

    // Format: ['a', 'b', 'c']
    if (trimmed[0] === "[" && trimmed[trimmed.length - 1] === "]"){
      try{
        const parsed = JSON.parse(trimmed.replace(/'/g, "\""));
        if (Array.isArray(parsed)){
          return parsed.map(v => String(v));
        }
      }catch(e){
        // Not parseable as array, keep as plain domain.
      }
    }

    return null;
  }

  static setEnumDomain(opt, values){
    if (!Array.isArray(values) || values.length === 0) return;

    const domain = [...new Set(values.map(v => String(v)))];
    const currentValue = opt.value !== undefined ? String(opt.value) : "";
    if (currentValue !== "" && domain.indexOf(currentValue) === -1){
      domain.unshift(currentValue);
    }

    opt.type = "enum";
    opt.domain = domain;
  }

  static normalizeCategoricalOption(opt, clusterNodeUrls = []){
    const name = String(opt.name || "").toLowerCase();
    const overrides = PresetUtils.getCategoricalOverrides();

    if (name in overrides && opt.type !== "enum"){
      PresetUtils.setEnumDomain(opt, overrides[name]);
      return;
    }

    if (name === "sm-cluster" || name === "clusterodm"){
      if (clusterNodeUrls.length > 0){
        PresetUtils.setEnumDomain(opt, clusterNodeUrls);
      }
      return;
    }

    // Fallback: sometimes enum domains are serialized as strings.
    if (opt.type !== "enum"){
      const parsedDomain = PresetUtils.parseDomainFromString(opt.domain);
      if (parsedDomain && parsedDomain.length > 0){
        PresetUtils.setEnumDomain(opt, parsedDomain);
      }
    }
  }

  // Merge a set of options specified in a preset with
  // those available from a processing node, while populating
  // an extra "defaultValue" field as appropriate
  // @return available options.
  static getAvailableOptions(presetOptions, nodeOptions, clusterNodeUrls = []){
    let result = Utils.clone(nodeOptions);

    result.forEach(opt => {
        if (!opt.defaultValue){
            let presetOpt;
            if (Array.isArray(presetOptions)){
              presetOpt = presetOptions.find(to => to.name == opt.name);
            }

            if (presetOpt){
              opt.defaultValue = opt.value;
              opt.value = presetOpt.value;
            }else{
              opt.defaultValue = opt.value !== undefined ? opt.value : "";
              delete(opt.value);
            }
        }

        PresetUtils.normalizeCategoricalOption(opt, clusterNodeUrls);

        if (typeof opt.help === "string"){
            opt.help = interpolate(_(opt.help), {
                choices: Array.isArray(opt.domain) ? opt.domain.join(", ") : opt.domain,
                'default': opt.defaultValue === "" ? "\"\"" : opt.defaultValue
            });
        }
    });

    // Sort by name ascending
    result.sort((a, b) => a.name < b.name ? -1 : 1);

    return result;
  }
}

export default PresetUtils;
