const yaml = require('js-yaml');
const fs   = require('fs');
const conf = yaml.safeLoad(fs.readFileSync('./serverless.conf.yml', 'utf8'));

module.exports.branchRoutes = () => {
  return JSON.stringify(Object.assign({}, ...conf.branchRouting.routes))
}