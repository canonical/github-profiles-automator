resource "juju_application" "github_profiles_automator" {
  charm {
    name     = "github-profiles-automator"
    channel  = var.channel
    revision = var.revision
  }
  config    = var.config
  model     = var.model_name
  name      = var.app_name
  resources = var.resources
  trust     = true
  units     = 1
}
