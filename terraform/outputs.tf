output "app_name" {
  value = juju_application.github_profiles_automator.name
}

output "provides" {
  value = {
    provide_cmr_mesh = "provide-cmr-mesh"
  }
}

output "requires" {
  value = {
    require_cmr_mesh = "require-cmr-mesh"
    service_mesh     = "service-mesh"
  }
}
