import Utils from '../Utils';

const { assert } = Utils;

const modelPreCheck = (options) => {
  assert(options.viewer !== undefined);
  assert(options.task !== undefined);
};

export default {
  namespace: "Model",

  endpoints: [
    ["willAddControls", modelPreCheck],
    ["didAddControls", modelPreCheck],
  ],

  functions: []
};
