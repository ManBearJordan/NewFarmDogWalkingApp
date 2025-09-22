<#
Seeds the standard label set used by the spec and workflows.
Run once in the repo root (after gh auth login).
#>
$labels = @(
  @{name='spec';          color='6f42c1'; desc='Specification / planning'},
  @{name='billing';       color='fbca04'; desc='Billing work'},
  @{name='stripe';        color='0e8a16'; desc='Stripe integration'},
  @{name='bookings';      color='1d76db'; desc='Bookings domain'},
  @{name='calendar';      color='0052cc'; desc='Calendar features'},
  @{name='subscriptions'; color='5319e7'; desc='Subscriptions & sync'},
  @{name='backend';       color='d93f0b'; desc='Backend / data model'},
  @{name='api';           color='0366d6'; desc='API & webhooks'},
  @{name='frontend';      color='bfdadc'; desc='Frontend / UI'},
  @{name='admin';         color='c2e0c6'; desc='Admin & settings'},
  @{name='devops';        color='5319e7'; desc='Deployment & ops'},
  @{name='security';      color='b60205'; desc='Security & privacy'},
  @{name='reports';       color='fef2c0'; desc='Reports & exports'},
  @{name='crm';           color='0b4f6c'; desc='Clients / CRM'}
)
$existing = (gh label list --limit 200 --json name | ConvertFrom-Json).name
foreach ($l in $labels) {
  if ($existing -notcontains $l.name) {
    gh label create $l.name --color $l.color --description $l.desc
    Write-Host "Created label $($l.name)"
  } else {
    gh label edit   $l.name --color $l.color --description $l.desc
    Write-Host "Updated label $($l.name)"
  }
}
