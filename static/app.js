async function refreshMetrics() {
  const data = await fetch('/api/metrics').then((r) => r.json())
  document.getElementById('metric-total').textContent = data.total_tickets
  document.getElementById('metric-reviewed').textContent = data.reviewed
  document.getElementById('metric-agreement').textContent =
    data.agreement_rate == null
      ? '—'
      : `${Math.round(data.agreement_rate * 100)}%`
  document.getElementById('metric-confidence').textContent =
    data.avg_confidence == null ? '—' : Number(data.avg_confidence).toFixed(2)
}

function showRecommendation(ticket) {
  document.getElementById('recommendation').hidden = false
  document.getElementById('rec-source').textContent = ticket.ai_source || 'mock'
  document.getElementById('rec-category').textContent = ticket.ai_category
  document.getElementById('rec-priority').textContent = ticket.ai_priority
  document.getElementById('rec-team').textContent = ticket.ai_team
  document.getElementById('rec-confidence').textContent = ticket.ai_confidence
  document.getElementById('rec-summary').textContent = ticket.ai_summary
  document.getElementById('rec-response').textContent =
    ticket.ai_suggested_response
  document.getElementById('review-ticket-id').value = ticket.id
  document.getElementById('review-status').textContent = ''
  document.getElementById('review-form').querySelector('button').disabled =
    ticket.status !== 'awaiting_review'
}

document.getElementById('ticket-form').addEventListener('submit', async (e) => {
  e.preventDefault()
  const status = document.getElementById('form-status')
  status.textContent = 'Submitting…'
  const form = e.target
  const body = {
    customer_name: form.customer_name.value,
    customer_tier: form.customer_tier.value,
    subject: form.subject.value,
    description: form.description.value,
  }
  const res = await fetch('/api/tickets', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    status.textContent = `Error ${res.status}`
    return
  }
  const ticket = await res.json()
  status.textContent = `Created ticket #${ticket.id}`
  showRecommendation(ticket)
  await refreshMetrics()
})

document.getElementById('review-form').addEventListener('submit', async (e) => {
  e.preventDefault()
  const status = document.getElementById('review-status')
  const ticketId = document.getElementById('review-ticket-id').value
  const approved = document.getElementById('review-approved').checked
  const finalPriority = document.getElementById('review-final-priority').value
  const body = {
    approved,
    final_priority: finalPriority || null,
    reviewer_note: document.getElementById('review-note').value || null,
  }
  status.textContent = 'Saving…'
  const res = await fetch(`/api/tickets/${ticketId}/review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    status.textContent = `Error ${res.status}`
    return
  }
  const ticket = await res.json()
  status.textContent = `Saved. Status: ${ticket.status}. Delivery: ${ticket.delivery_status}`
  e.target.querySelector('button').disabled = true
  await refreshMetrics()
})

refreshMetrics()
