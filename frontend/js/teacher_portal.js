/**
 * Teacher Portal Module — All 9 portal sections
 * Namespace: window.TP
 * Hooks into existing app.js navigation + Api client
 */

const TP = (() => {
  // ─────────────────────────────────────────────────────────────────
  // STATE
  // ─────────────────────────────────────────────────────────────────
  let _dashboard = null;
  let _myClasses = null;
  let _assignmentModalMode = 'create';
  let _assignmentEditId = null;

  // ─────────────────────────────────────────────────────────────────
  // HELPERS
  // ─────────────────────────────────────────────────────────────────
  function el(id) { return document.getElementById(id); }

  function statusBadge(status) {
    const map = {
      DRAFT:      'bg-secondary',
      PUBLISHED:  'bg-success',
      CLOSED:     'bg-dark',
      SUBMITTED:  'bg-primary',
      GRADED:     'bg-success',
      LATE:       'bg-warning text-dark',
      NOT_SUBMITTED: 'bg-danger',
      SCHEDULED:  'bg-info text-dark',
      LIVE:       'bg-danger',
      COMPLETED:  'bg-success',
      CANCELLED:  'bg-secondary',
      NORMAL:     'bg-secondary',
      URGENT:     'bg-warning text-dark',
      CRITICAL:   'bg-danger',
    };
    const css = map[status] || 'bg-secondary';
    return `<span class="badge ${css} rounded-pill">${status}</span>`;
  }

  function typeIcon(type) {
    const icons = {
      EVENT: 'bi-calendar-star text-primary',
      EXAM: 'bi-clipboard2-check text-danger',
      ASSIGNMENT_DEADLINE: 'bi-file-earmark-text text-warning',
      ONLINE_CLASS: 'bi-camera-video text-success',
    };
    return `<i class="bi ${icons[type] || 'bi-circle'} me-1"></i>`;
  }

  function fmtDate(iso) {
    if (!iso) return '—';
    const d = new Date(iso);
    return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
  }

  function fmtDateTime(iso) {
    if (!iso) return '—';
    const d = new Date(iso);
    return d.toLocaleString('en-IN', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  }

  function setHtml(id, html) {
    const el_ = el(id);
    if (el_) el_.innerHTML = html;
  }

  function showToast(msg, type = 'success') {
    const toastContainer = document.getElementById('app-toast-container');
    if (!toastContainer) { console.log('[TP Toast]', type, msg); return; }
    const id = 'tp-toast-' + Date.now();
    const bgMap = { success: 'bg-success', danger: 'bg-danger', warning: 'bg-warning text-dark', info: 'bg-info text-dark' };
    const bg = bgMap[type] || 'bg-secondary';
    const toastHtml = `
      <div id="${id}" class="toast align-items-center text-white ${bg} border-0 mb-2" role="alert" data-bs-autohide="true" data-bs-delay="4000">
        <div class="d-flex">
          <div class="toast-body fw-medium small">${msg}</div>
          <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
      </div>`;
    toastContainer.insertAdjacentHTML('beforeend', toastHtml);
    const toastEl = document.getElementById(id);
    if (toastEl) new bootstrap.Toast(toastEl).show();
  }

  function emptyState(icon, msg) {
    return `<div class="tp-empty-state"><i class="bi ${icon} fs-2 mb-2 text-muted"></i><p class="mb-0 text-muted">${msg}</p></div>`;
  }

  function spinner(color = 'primary') {
    return `<div class="text-center py-5"><div class="spinner-border text-${color}" role="status"><span class="visually-hidden">Loading...</span></div></div>`;
  }

  function errorState(msg) {
    return `<div class="tp-empty-state text-danger"><i class="bi bi-exclamation-triangle-fill fs-2 mb-2"></i><p class="mb-0">${msg}</p></div>`;
  }

  // ─────────────────────────────────────────────────────────────────
  // TAB SWITCHING
  // ─────────────────────────────────────────────────────────────────
  function switchTab(tabId) {
    document.querySelectorAll('.tp-tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tp-tab-content').forEach(c => c.classList.remove('active'));

    const btn = el(tabId);
    if (btn) btn.classList.add('active');

    const contentId = tabId.replace('tp-tab-', 'tp-content-');
    const content = el(contentId);
    if (content) content.classList.add('active');

    // Lazy-load content on first visit
    const tab = tabId.replace('tp-tab-', '');
    switch(tab) {
      case 'classes':      loadMyClasses(); break;
      case 'assignments':  loadAssignments(); break;
      case 'online-classes': loadOnlineClasses(); break;
      case 'materials':    loadMaterials(); break;
      case 'timetable':    loadTimetable(); break;
      case 'calendar':     loadCalendar(); break;
      case 'announcements': loadAnnouncements(); break;
      case 'performance':  loadPerformance(); break;
    }
  }

  // ─────────────────────────────────────────────────────────────────
  // 1. DASHBOARD
  // ─────────────────────────────────────────────────────────────────
  async function loadDashboard() {
    try {
      const data = await Api.tpDashboard();
      _dashboard = data;

      // Hero header
      const nameEl = el('tp-teacher-name-header');
      const roleEl = el('tp-teacher-role-header');
      if (nameEl) nameEl.textContent = data.teacher_name || 'Teacher Dashboard';
      if (roleEl) roleEl.textContent = `${data.role || ''} · ${data.department || ''}`;

      // KPI
      setHtml('tp-stat-classes', data.total_assigned_classes ?? '—');
      setHtml('tp-stat-subjects', data.total_assigned_subjects ?? '—');
      setHtml('tp-stat-students', data.total_students ?? '—');
      setHtml('tp-stat-assignments', data.total_assignments ?? '—');
      setHtml('tp-stat-pending', data.pending_evaluations ?? '—');
      setHtml('tp-stat-materials', data.total_study_materials ?? '—');

      // Today label
      const todayLabel = el('tp-today-label');
      const days = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];
      if (todayLabel) todayLabel.textContent = days[new Date().getDay()];

      // Today's timetable
      renderTodayTimetable(data.todays_timetable || []);

      // Upcoming online classes
      renderUpcomingOC(data.upcoming_online_classes || []);

      // Pending evaluations
      renderPendingEvals(data.pending_submission_details || [], data.pending_evaluations);

      // Recent announcements
      renderRecentAnnouncements(data.recent_announcements || []);

    } catch(err) {
      console.error('[TP] Dashboard error:', err.message);
      setHtml('tp-today-timetable', errorState('Could not load dashboard: ' + err.message));
    }
  }

  function renderTodayTimetable(slots) {
    if (!slots.length) {
      setHtml('tp-today-timetable', emptyState('bi-calendar-check', 'No classes scheduled for today'));
      return;
    }
    const rows = slots.map(s => `
      <div class="d-flex align-items-center gap-3 p-2 mb-2 rounded-3 border bg-light">
        <div class="tp-period-badge">${s.period}</div>
        <div class="flex-grow-1">
          <div class="fw-semibold small">${s.subject_name} <span class="text-muted">(${s.subject_code})</span></div>
          <div class="text-muted small"><i class="bi bi-building me-1"></i>${s.class_name}${s.classroom ? ' · ' + s.classroom : ''}</div>
        </div>
        <div class="text-end small text-secondary">
          <div>${s.start_time || ''}</div>
          <div>${s.end_time || ''}</div>
        </div>
      </div>`).join('');
    setHtml('tp-today-timetable', rows);
  }

  function renderUpcomingOC(ocs) {
    if (!ocs.length) {
      setHtml('tp-upcoming-oc', emptyState('bi-camera-video', 'No upcoming online classes'));
      return;
    }
    const rows = ocs.map(oc => `
      <div class="d-flex align-items-start gap-3 p-2 mb-2 rounded-3 border">
        <div class="stat-icon success" style="width:36px;height:36px;font-size:0.9rem"><i class="bi bi-camera-video-fill"></i></div>
        <div class="flex-grow-1 overflow-hidden">
          <div class="fw-semibold small text-truncate">${oc.title}</div>
          <div class="text-muted small">${oc.subject_name} · ${oc.class_name}</div>
          <div class="text-muted small"><i class="bi bi-clock me-1"></i>${fmtDateTime(oc.start_time)}</div>
        </div>
        <div>${statusBadge(oc.status)}</div>
      </div>`).join('');
    setHtml('tp-upcoming-oc', rows);
  }

  function renderPendingEvals(subs, totalCount) {
    if (!subs.length) {
      setHtml('tp-pending-evals', emptyState('bi-check-circle', 'All submissions graded!'));
      return;
    }
    const rows = subs.map(sub => `
      <div class="d-flex align-items-center gap-2 p-2 mb-2 rounded-3 border">
        <div class="stat-icon warning" style="width:32px;height:32px;font-size:0.8rem"><i class="bi bi-pencil-square"></i></div>
        <div class="flex-grow-1 overflow-hidden">
          <div class="fw-semibold small text-truncate">${sub.assignment_title}</div>
          <div class="text-muted small">${sub.student_name} (${sub.student_roll})</div>
          <div class="text-muted small"><i class="bi bi-calendar me-1"></i>${fmtDate(sub.submitted_date)}</div>
        </div>
        <button class="btn btn-sm btn-outline-warning" onclick="TP.openGradeSubmissionModal(${sub.assignment_id}, ${sub.submission_id})">
          <i class="bi bi-pencil-fill"></i>
        </button>
      </div>`).join('');
    const extra = totalCount > 5 ? `<div class="text-center small text-muted py-2">+${totalCount - 5} more pending</div>` : '';
    setHtml('tp-pending-evals', rows + extra);
  }

  function renderRecentAnnouncements(anns) {
    if (!anns.length) {
      setHtml('tp-recent-announcements', emptyState('bi-megaphone', 'No recent announcements'));
      return;
    }
    const priorityColors = { NORMAL: 'secondary', URGENT: 'warning', CRITICAL: 'danger' };
    const rows = anns.map(a => {
      const color = priorityColors[a.priority] || 'secondary';
      return `
        <div class="p-2 mb-2 rounded-3 border border-${color} bg-${color}-subtle">
          <div class="d-flex justify-content-between align-items-start gap-2">
            <div class="fw-semibold small">${a.title}</div>
            ${statusBadge(a.priority)}
          </div>
          <p class="text-muted small mb-1 mt-1">${(a.message || '').substring(0, 150)}${(a.message||'').length > 150 ? '…' : ''}</p>
          <div class="text-muted small"><i class="bi bi-person me-1"></i>${a.author} · ${fmtDate(a.publication_date)}</div>
        </div>`;
    }).join('');
    setHtml('tp-recent-announcements', rows);
  }

  // ─────────────────────────────────────────────────────────────────
  // 2. MY CLASSES
  // ─────────────────────────────────────────────────────────────────
  async function loadMyClasses() {
    setHtml('tp-classes-list', spinner());
    try {
      const data = await Api.tpMyClasses();
      _myClasses = data.classes || [];
      if (!_myClasses.length) {
        setHtml('tp-classes-list', emptyState('bi-building', 'No classes assigned to you yet. Contact admin.'));
        return;
      }
      const cards = _myClasses.map(c => `
        <div class="card card-custom mb-3">
          <div class="d-flex flex-wrap justify-content-between align-items-center p-3 border-bottom gap-2">
            <div>
              <h6 class="fw-bold mb-0">${c.name || 'Unnamed Class'}</h6>
              <div class="text-muted small">${c.department || ''} · Year ${c.year || ''} · Section ${c.section || ''}</div>
            </div>
            <div class="d-flex gap-2 align-items-center flex-wrap">
              ${(c.subjects || []).map(s => `<span class="badge bg-primary-subtle text-primary border border-primary-subtle">${s.code || ''} - ${s.name || ''}</span>`).join('')}
              <span class="badge bg-success-subtle text-success border border-success-subtle"><i class="bi bi-people-fill me-1"></i>${c.student_count ?? (c.students || []).length} Students</span>
            </div>
          </div>
          <div class="p-3">
            <h6 class="small fw-semibold text-muted text-uppercase mb-2" style="letter-spacing:.05em">Student Roster</h6>
            <div class="table-responsive">
              <table class="table table-sm table-hover align-middle mb-0">
                <thead class="table-light">
                  <tr><th>Roll No</th><th>Name</th><th>Email</th><th>Status</th><th>Face</th></tr>
                </thead>
                <tbody>
                  ${(c.students || []).map(s => `
                    <tr>
                      <td class="fw-semibold small">${s.roll_number || '—'}</td>
                      <td class="small">${s.full_name || '—'}</td>
                      <td class="small text-muted">${s.email || '—'}</td>
                      <td>${s.is_active ? '<span class="badge bg-success-subtle text-success">Active</span>' : '<span class="badge bg-secondary-subtle text-secondary">Inactive</span>'}</td>
                      <td>${s.face_enrolled ? '<span class="badge bg-primary-subtle text-primary"><i class="bi bi-person-bounding-box me-1"></i>Enrolled</span>' : '<span class="badge bg-danger-subtle text-danger">Pending</span>'}</td>
                    </tr>`).join('')}
                  ${!(c.students || []).length ? '<tr><td colspan="5" class="text-center text-muted py-3">No students in this class</td></tr>' : ''}
                </tbody>
              </table>
            </div>
          </div>
        </div>`).join('');
      setHtml('tp-classes-list', cards);
    } catch(err) {
      setHtml('tp-classes-list', errorState('Failed to load classes: ' + err.message));
    }
  }

  // ─────────────────────────────────────────────────────────────────
  // 3. ASSIGNMENTS
  // ─────────────────────────────────────────────────────────────────
  async function loadAssignments() {
    setHtml('tp-assignments-table', spinner());
    try {
      const statusFilter = (el('tp-assign-filter-status') || {}).value || '';
      const data = await Api.tpListAssignments(statusFilter ? { assignment_status: statusFilter } : {});
      if (!data.length) {
        setHtml('tp-assignments-table', emptyState('bi-file-earmark-text', 'No assignments yet. Click "New Assignment" to create one.'));
        return;
      }
      const rows = data.map(a => `
        <tr>
          <td>
            <div class="fw-semibold small">${a.title}</div>
            <div class="text-muted small">${(a.description || '').substring(0, 60)}${(a.description||'').length>60?'…':''}</div>
          </td>
          <td class="small">${a.class_name || '—'}</td>
          <td class="small">${a.subject_name || '—'} <span class="text-muted">(${a.subject_code || ''})</span></td>
          <td class="small">${fmtDate(a.deadline)}</td>
          <td class="text-center small">${a.maximum_marks}</td>
          <td>${statusBadge(a.status)}</td>
          <td class="text-center small">
            <span class="badge bg-secondary-subtle text-secondary me-1">${a.submission_count} submitted</span>
            ${a.pending_evaluations > 0 ? `<span class="badge bg-warning text-dark">${a.pending_evaluations} to grade</span>` : ''}
          </td>
          <td>
            <div class="d-flex gap-1">
              <button class="btn btn-sm btn-outline-primary" onclick="TP.viewSubmissions(${a.id}, '${(a.title||'').replace(/'/g,'')}')" title="View Submissions">
                <i class="bi bi-collection-fill"></i>
              </button>
              <button class="btn btn-sm btn-outline-secondary" onclick="TP.openAssignmentModal(${JSON.stringify(a).replace(/"/g,'&quot;')})" title="Edit">
                <i class="bi bi-pencil-fill"></i>
              </button>
              <button class="btn btn-sm btn-outline-danger" onclick="TP.deleteAssignment(${a.id})" title="Delete">
                <i class="bi bi-trash-fill"></i>
              </button>
            </div>
          </td>
        </tr>`).join('');
      setHtml('tp-assignments-table', `
        <div class="table-responsive">
          <table class="table table-hover align-middle mb-0">
            <thead class="table-light">
              <tr>
                <th>Title</th><th>Class</th><th>Subject</th><th>Deadline</th>
                <th class="text-center">Max Marks</th><th>Status</th><th>Submissions</th><th>Actions</th>
              </tr>
            </thead>
            <tbody>${rows}</tbody>
          </table>
        </div>`);
    } catch(err) {
      setHtml('tp-assignments-table', errorState('Failed to load assignments: ' + err.message));
    }
  }

  function openAssignmentModal(assignmentData = null) {
    _assignmentModalMode = assignmentData ? 'edit' : 'create';
    _assignmentEditId = assignmentData ? assignmentData.id : null;

    const classes = _myClasses || [];
    const classOptions = classes.map(c =>
      `<option value="${c.id}" ${assignmentData && assignmentData.class_id == c.id ? 'selected' : ''}>${c.name}</option>`
    ).join('');

    // Collect all subjects
    const subjectsMap = {};
    (classes || []).forEach(c => (c.subjects || []).forEach(s => { subjectsMap[s.id] = s; }));
    const subjectOptions = Object.values(subjectsMap).map(s =>
      `<option value="${s.id}" ${assignmentData && assignmentData.subject_id == s.id ? 'selected' : ''}>${s.name} (${s.code})</option>`
    ).join('');

    const modal = document.createElement('div');
    modal.className = 'modal fade';
    modal.id = 'tp-assignment-modal';
    modal.tabIndex = -1;
    modal.innerHTML = `
      <div class="modal-dialog modal-lg">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title fw-bold"><i class="bi bi-file-earmark-text me-2 text-primary"></i>${_assignmentModalMode === 'create' ? 'New Assignment' : 'Edit Assignment'}</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
          </div>
          <div class="modal-body">
            <form id="tp-assignment-form">
              <div class="row g-3">
                <div class="col-12">
                  <label class="form-label fw-semibold small">Title *</label>
                  <input type="text" id="tp-assign-title" class="form-control" value="${assignmentData ? assignmentData.title : ''}" required>
                </div>
                <div class="col-md-6">
                  <label class="form-label fw-semibold small">Class *</label>
                  <select id="tp-assign-class" class="form-select" required>
                    <option value="">Select class…</option>${classOptions}
                  </select>
                </div>
                <div class="col-md-6">
                  <label class="form-label fw-semibold small">Subject *</label>
                  <select id="tp-assign-subject" class="form-select" required>
                    <option value="">Select subject…</option>${subjectOptions}
                  </select>
                </div>
                <div class="col-md-6">
                  <label class="form-label fw-semibold small">Deadline</label>
                  <input type="datetime-local" id="tp-assign-deadline" class="form-control" value="${assignmentData && assignmentData.deadline ? assignmentData.deadline.slice(0,16) : ''}">
                </div>
                <div class="col-md-6">
                  <label class="form-label fw-semibold small">Max Marks</label>
                  <input type="number" id="tp-assign-marks" class="form-control" min="1" max="1000" value="${assignmentData ? assignmentData.maximum_marks : 100}">
                </div>
                <div class="col-md-6">
                  <label class="form-label fw-semibold small">Status</label>
                  <select id="tp-assign-status" class="form-select">
                    <option value="DRAFT" ${!assignmentData || assignmentData.status === 'DRAFT' ? 'selected' : ''}>Draft</option>
                    <option value="PUBLISHED" ${assignmentData && assignmentData.status === 'PUBLISHED' ? 'selected' : ''}>Published</option>
                    <option value="CLOSED" ${assignmentData && assignmentData.status === 'CLOSED' ? 'selected' : ''}>Closed</option>
                  </select>
                </div>
                <div class="col-md-6">
                  <label class="form-label fw-semibold small">Attachment URL</label>
                  <input type="url" id="tp-assign-attachments" class="form-control" placeholder="https://…" value="${assignmentData && assignmentData.attachments ? assignmentData.attachments : ''}">
                </div>
                <div class="col-12">
                  <label class="form-label fw-semibold small">Instructions / Description</label>
                  <textarea id="tp-assign-desc" class="form-control" rows="3">${assignmentData ? (assignmentData.description || '') : ''}</textarea>
                </div>
              </div>
            </form>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
            <button class="btn btn-primary" onclick="TP.submitAssignmentForm()">
              <i class="bi bi-check-lg me-1"></i>${_assignmentModalMode === 'create' ? 'Create' : 'Save Changes'}
            </button>
          </div>
        </div>
      </div>`;
    document.body.appendChild(modal);
    const bsModal = new bootstrap.Modal(modal);
    bsModal.show();
    modal.addEventListener('hidden.bs.modal', () => modal.remove());
  }

  async function submitAssignmentForm() {
    const data = {
      title: (el('tp-assign-title') || {}).value?.trim(),
      class_id: parseInt((el('tp-assign-class') || {}).value),
      subject_id: parseInt((el('tp-assign-subject') || {}).value),
      deadline: (el('tp-assign-deadline') || {}).value || null,
      maximum_marks: parseInt((el('tp-assign-marks') || {}).value) || 100,
      status: (el('tp-assign-status') || {}).value || 'DRAFT',
      description: (el('tp-assign-desc') || {}).value?.trim() || null,
      attachments: (el('tp-assign-attachments') || {}).value?.trim() || null,
    };
    if (!data.title || !data.class_id || !data.subject_id) {
      showToast('Title, Class, and Subject are required.', 'warning');
      return;
    }
    try {
      if (_assignmentModalMode === 'create') {
        await Api.tpCreateAssignment(data);
        showToast('Assignment created successfully!', 'success');
      } else {
        await Api.tpUpdateAssignment(_assignmentEditId, data);
        showToast('Assignment updated!', 'success');
      }
      bootstrap.Modal.getInstance(el('tp-assignment-modal'))?.hide();
      await loadAssignments();
      await loadDashboard();
    } catch(err) {
      showToast('Error: ' + err.message, 'danger');
    }
  }

  async function deleteAssignment(id) {
    if (!confirm('Delete this assignment? All submissions will be lost.')) return;
    try {
      await Api.tpDeleteAssignment(id);
      showToast('Assignment deleted.', 'success');
      await loadAssignments();
    } catch(err) {
      showToast('Error: ' + err.message, 'danger');
    }
  }

  async function viewSubmissions(assignmentId, title) {
    const subs = await Api.tpListSubmissions(assignmentId).catch(e => { showToast(e.message, 'danger'); return []; });

    const statusColors = { SUBMITTED: 'primary', GRADED: 'success', LATE: 'warning', NOT_SUBMITTED: 'danger' };
    const rows = subs.map(s => `
      <tr>
        <td class="small fw-semibold">${s.student_roll}</td>
        <td class="small">${s.student_name}</td>
        <td class="small">${fmtDate(s.submitted_date)}</td>
        <td>${statusBadge(s.submission_status)}</td>
        <td class="text-center small">${s.marks != null ? `${s.marks}/${s.max_marks}` : '—'}</td>
        <td class="small text-muted">${(s.feedback || '').substring(0,60) || '—'}</td>
        <td>
          <button class="btn btn-sm btn-outline-success" onclick="TP.openGradeSubmissionModal(${assignmentId}, ${s.id})">
            <i class="bi bi-pencil-fill"></i> Grade
          </button>
          ${s.uploaded_file ? `<a class="btn btn-sm btn-outline-primary ms-1" href="${s.uploaded_file}" target="_blank"><i class="bi bi-download"></i></a>` : ''}
        </td>
      </tr>`).join('');

    const modal = document.createElement('div');
    modal.className = 'modal fade';
    modal.id = 'tp-subs-modal';
    modal.tabIndex = -1;
    modal.innerHTML = `
      <div class="modal-dialog modal-xl">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title fw-bold"><i class="bi bi-collection-fill me-2 text-primary"></i>Submissions: ${title}</h5>
            <button class="btn-close" data-bs-dismiss="modal"></button>
          </div>
          <div class="modal-body p-0">
            ${subs.length ? `
            <div class="table-responsive">
              <table class="table table-hover align-middle mb-0">
                <thead class="table-light"><tr><th>Roll No</th><th>Name</th><th>Submitted</th><th>Status</th><th class="text-center">Marks</th><th>Feedback</th><th>Actions</th></tr></thead>
                <tbody>${rows}</tbody>
              </table>
            </div>` : emptyState('bi-inbox', 'No submissions yet')}
          </div>
          <div class="modal-footer"><button class="btn btn-secondary" data-bs-dismiss="modal">Close</button></div>
        </div>
      </div>`;
    document.body.appendChild(modal);
    const bsModal = new bootstrap.Modal(modal);
    bsModal.show();
    modal.addEventListener('hidden.bs.modal', () => modal.remove());
  }

  function openGradeSubmissionModal(assignmentId, submissionId) {
    const existing = document.getElementById('tp-grade-modal');
    if (existing) existing.remove();

    const modal = document.createElement('div');
    modal.className = 'modal fade';
    modal.id = 'tp-grade-modal';
    modal.tabIndex = -1;
    modal.innerHTML = `
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title fw-bold"><i class="bi bi-pencil-fill me-2 text-success"></i>Grade Submission</h5>
            <button class="btn-close" data-bs-dismiss="modal"></button>
          </div>
          <div class="modal-body">
            <div class="mb-3">
              <label class="form-label fw-semibold small">Marks Awarded</label>
              <input type="number" id="tp-grade-marks" class="form-control" min="0" placeholder="e.g. 85">
            </div>
            <div class="mb-3">
              <label class="form-label fw-semibold small">Feedback (optional)</label>
              <textarea id="tp-grade-feedback" class="form-control" rows="3" placeholder="Great work! …"></textarea>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
            <button class="btn btn-success" onclick="TP.submitGrade(${assignmentId}, ${submissionId})">
              <i class="bi bi-check-lg me-1"></i>Submit Grade
            </button>
          </div>
        </div>
      </div>`;
    document.body.appendChild(modal);
    new bootstrap.Modal(modal).show();
    modal.addEventListener('hidden.bs.modal', () => modal.remove());
  }

  async function submitGrade(assignmentId, submissionId) {
    const marks = parseFloat((el('tp-grade-marks') || {}).value);
    const feedback = (el('tp-grade-feedback') || {}).value?.trim();
    if (isNaN(marks)) { showToast('Please enter valid marks.', 'warning'); return; }
    try {
      await Api.tpGradeSubmission(assignmentId, submissionId, { marks, feedback, submission_status: 'GRADED' });
      showToast('Graded successfully!', 'success');
      bootstrap.Modal.getInstance(el('tp-grade-modal'))?.hide();
      await loadDashboard();
    } catch(err) {
      showToast('Error: ' + err.message, 'danger');
    }
  }

  // ─────────────────────────────────────────────────────────────────
  // 4. ONLINE CLASSES
  // ─────────────────────────────────────────────────────────────────
  async function loadOnlineClasses() {
    setHtml('tp-oc-list', spinner('success'));
    try {
      const data = await Api.tpListOnlineClasses();
      if (!data.length) {
        setHtml('tp-oc-list', emptyState('bi-camera-video', 'No online classes scheduled yet.'));
        return;
      }
      const providerIcons = { 'Google Meet': 'bi-camera-video-fill text-success', 'Zoom': 'bi-camera-video-fill text-primary', 'Teams': 'bi-camera-video-fill text-info' };
      const cards = data.map(oc => `
        <div class="col-md-6 col-xl-4">
          <div class="card card-custom h-100">
            <div class="card-body">
              <div class="d-flex justify-content-between align-items-start mb-2">
                <div>
                  <h6 class="fw-bold mb-1">${oc.title}</h6>
                  <div class="text-muted small">${oc.subject_name || '—'} · ${oc.class_name || '—'}</div>
                </div>
                ${statusBadge(oc.status)}
              </div>
              <div class="small text-muted mb-1"><i class="bi bi-clock me-1"></i>${fmtDateTime(oc.start_time)}</div>
              ${oc.end_time ? `<div class="small text-muted mb-2"><i class="bi bi-clock-history me-1"></i>Ends: ${fmtDateTime(oc.end_time)}</div>` : ''}
              <div class="d-flex gap-2 mt-2">
                ${oc.meeting_url ? `<a href="${oc.meeting_url}" target="_blank" class="btn btn-sm btn-success"><i class="bi bi-box-arrow-up-right me-1"></i>Join</a>` : ''}
                <button class="btn btn-sm btn-outline-danger ms-auto" onclick="TP.deleteOnlineClass(${oc.id})">
                  <i class="bi bi-trash-fill"></i>
                </button>
              </div>
            </div>
          </div>
        </div>`).join('');
      setHtml('tp-oc-list', `<div class="row g-3">${cards}</div>`);
    } catch(err) {
      setHtml('tp-oc-list', errorState('Failed to load online classes: ' + err.message));
    }
  }

  function openOnlineClassModal() {
    const classes = _myClasses || [];
    const classOptions = classes.map(c => `<option value="${c.id}">${c.name}</option>`).join('');
    const subjectsMap = {};
    classes.forEach(c => (c.subjects || []).forEach(s => { subjectsMap[s.id] = s; }));
    const subjectOptions = Object.values(subjectsMap).map(s => `<option value="${s.id}">${s.name} (${s.code})</option>`).join('');

    const modal = document.createElement('div');
    modal.className = 'modal fade';
    modal.id = 'tp-oc-modal';
    modal.tabIndex = -1;
    modal.innerHTML = `
      <div class="modal-dialog modal-lg">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title fw-bold"><i class="bi bi-camera-video-fill me-2 text-success"></i>Schedule Online Class</h5>
            <button class="btn-close" data-bs-dismiss="modal"></button>
          </div>
          <div class="modal-body">
            <div class="row g-3">
              <div class="col-12">
                <label class="form-label fw-semibold small">Class Title *</label>
                <input type="text" id="tp-oc-title" class="form-control" placeholder="e.g. Lecture 5: Algorithms">
              </div>
              <div class="col-md-6">
                <label class="form-label fw-semibold small">Class *</label>
                <select id="tp-oc-class" class="form-select"><option value="">Select…</option>${classOptions}</select>
              </div>
              <div class="col-md-6">
                <label class="form-label fw-semibold small">Subject *</label>
                <select id="tp-oc-subject" class="form-select"><option value="">Select…</option>${subjectOptions}</select>
              </div>
              <div class="col-md-6">
                <label class="form-label fw-semibold small">Meeting Provider</label>
                <select id="tp-oc-provider" class="form-select">
                  <option value="Google Meet">Google Meet</option>
                  <option value="Zoom">Zoom</option>
                  <option value="Microsoft Teams">Microsoft Teams</option>
                  <option value="Other">Other</option>
                </select>
              </div>
              <div class="col-md-6">
                <label class="form-label fw-semibold small">Meeting URL *</label>
                <input type="url" id="tp-oc-url" class="form-control" placeholder="https://meet.google.com/…">
              </div>
              <div class="col-md-6">
                <label class="form-label fw-semibold small">Start Time *</label>
                <input type="datetime-local" id="tp-oc-start" class="form-control">
              </div>
              <div class="col-md-6">
                <label class="form-label fw-semibold small">End Time</label>
                <input type="datetime-local" id="tp-oc-end" class="form-control">
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
            <button class="btn btn-success" onclick="TP.submitOnlineClassForm()"><i class="bi bi-check-lg me-1"></i>Schedule</button>
          </div>
        </div>
      </div>`;
    document.body.appendChild(modal);
    new bootstrap.Modal(modal).show();
    modal.addEventListener('hidden.bs.modal', () => modal.remove());
  }

  async function submitOnlineClassForm() {
    const data = {
      title: (el('tp-oc-title')||{}).value?.trim(),
      class_id: parseInt((el('tp-oc-class')||{}).value),
      subject_id: parseInt((el('tp-oc-subject')||{}).value),
      meeting_provider: (el('tp-oc-provider')||{}).value,
      meeting_url: (el('tp-oc-url')||{}).value?.trim(),
      start_time: (el('tp-oc-start')||{}).value || null,
      end_time: (el('tp-oc-end')||{}).value || null,
      status: 'SCHEDULED',
    };
    if (!data.title || !data.class_id || !data.subject_id || !data.meeting_url || !data.start_time) {
      showToast('Title, Class, Subject, Meeting URL and Start Time are required.', 'warning');
      return;
    }
    try {
      await Api.tpCreateOnlineClass(data);
      showToast('Online class scheduled!', 'success');
      bootstrap.Modal.getInstance(el('tp-oc-modal'))?.hide();
      await loadOnlineClasses();
      await loadDashboard();
    } catch(err) {
      showToast('Error: ' + err.message, 'danger');
    }
  }

  async function deleteOnlineClass(id) {
    if (!confirm('Cancel this online class?')) return;
    try {
      await Api.tpDeleteOnlineClass(id);
      showToast('Online class cancelled.', 'success');
      await loadOnlineClasses();
    } catch(err) {
      showToast('Error: ' + err.message, 'danger');
    }
  }

  // ─────────────────────────────────────────────────────────────────
  // 5. STUDY MATERIALS
  // ─────────────────────────────────────────────────────────────────
  async function loadMaterials() {
    setHtml('tp-materials-list', spinner('warning'));
    try {
      const data = await Api.tpListMaterials();
      if (!data.length) {
        setHtml('tp-materials-list', emptyState('bi-folder', 'No study materials uploaded yet.'));
        return;
      }
      const rows = data.map(m => `
        <tr>
          <td>
            <div class="fw-semibold small">${m.title}</div>
            <div class="text-muted small">${(m.description||'').substring(0,60)}</div>
          </td>
          <td class="small">${m.class_name || '—'}</td>
          <td class="small">${m.subject_name || '—'}</td>
          <td class="small">${fmtDate(m.uploaded_date)}</td>
          <td class="small">${m.file_size_bytes ? Math.round(m.file_size_bytes/1024) + ' KB' : '—'}</td>
          <td>
            <div class="d-flex gap-1">
              ${m.file_url ? `<a class="btn btn-sm btn-outline-primary" href="${m.file_url}" target="_blank" title="Download"><i class="bi bi-download"></i></a>` : ''}
              <button class="btn btn-sm btn-outline-danger" onclick="TP.deleteMaterial(${m.id})" title="Delete"><i class="bi bi-trash-fill"></i></button>
            </div>
          </td>
        </tr>`).join('');
      setHtml('tp-materials-list', `
        <div class="table-responsive">
          <table class="table table-hover align-middle mb-0">
            <thead class="table-light"><tr><th>Title</th><th>Class</th><th>Subject</th><th>Uploaded</th><th>Size</th><th>Actions</th></tr></thead>
            <tbody>${rows}</tbody>
          </table>
        </div>`);
    } catch(err) {
      setHtml('tp-materials-list', errorState('Failed to load materials: ' + err.message));
    }
  }

  function openMaterialModal() {
    const classes = _myClasses || [];
    const classOptions = classes.map(c => `<option value="${c.id}">${c.name}</option>`).join('');
    const subjectsMap = {};
    classes.forEach(c => (c.subjects || []).forEach(s => { subjectsMap[s.id] = s; }));
    const subjectOptions = Object.values(subjectsMap).map(s => `<option value="${s.id}">${s.name} (${s.code})</option>`).join('');

    const modal = document.createElement('div');
    modal.className = 'modal fade';
    modal.id = 'tp-material-modal';
    modal.tabIndex = -1;
    modal.innerHTML = `
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title fw-bold"><i class="bi bi-folder-plus me-2 text-warning"></i>Add Study Material</h5>
            <button class="btn-close" data-bs-dismiss="modal"></button>
          </div>
          <div class="modal-body">
            <div class="row g-3">
              <div class="col-12">
                <label class="form-label fw-semibold small">Title *</label>
                <input type="text" id="tp-mat-title" class="form-control" placeholder="e.g. Chapter 3 Notes">
              </div>
              <div class="col-md-6">
                <label class="form-label fw-semibold small">Class *</label>
                <select id="tp-mat-class" class="form-select"><option value="">Select…</option>${classOptions}</select>
              </div>
              <div class="col-md-6">
                <label class="form-label fw-semibold small">Subject *</label>
                <select id="tp-mat-subject" class="form-select"><option value="">Select…</option>${subjectOptions}</select>
              </div>
              <div class="col-12">
                <label class="form-label fw-semibold small">File URL *</label>
                <input type="url" id="tp-mat-url" class="form-control" placeholder="https://drive.google.com/…">
              </div>
              <div class="col-md-6">
                <label class="form-label fw-semibold small">File Size (bytes)</label>
                <input type="number" id="tp-mat-size" class="form-control" min="0" placeholder="e.g. 204800">
              </div>
              <div class="col-12">
                <label class="form-label fw-semibold small">Description</label>
                <textarea id="tp-mat-desc" class="form-control" rows="2"></textarea>
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
            <button class="btn btn-warning text-white" onclick="TP.submitMaterialForm()"><i class="bi bi-cloud-upload me-1"></i>Upload</button>
          </div>
        </div>
      </div>`;
    document.body.appendChild(modal);
    new bootstrap.Modal(modal).show();
    modal.addEventListener('hidden.bs.modal', () => modal.remove());
  }

  async function submitMaterialForm() {
    const data = {
      title: (el('tp-mat-title')||{}).value?.trim(),
      class_id: parseInt((el('tp-mat-class')||{}).value),
      subject_id: parseInt((el('tp-mat-subject')||{}).value),
      file_url: (el('tp-mat-url')||{}).value?.trim(),
      file_size_bytes: parseInt((el('tp-mat-size')||{}).value) || null,
      description: (el('tp-mat-desc')||{}).value?.trim() || null,
    };
    if (!data.title || !data.class_id || !data.subject_id || !data.file_url) {
      showToast('Title, Class, Subject, and File URL are required.', 'warning');
      return;
    }
    try {
      await Api.tpCreateMaterial(data);
      showToast('Study material uploaded!', 'success');
      bootstrap.Modal.getInstance(el('tp-material-modal'))?.hide();
      await loadMaterials();
    } catch(err) {
      showToast('Error: ' + err.message, 'danger');
    }
  }

  async function deleteMaterial(id) {
    if (!confirm('Delete this study material?')) return;
    try {
      await Api.tpDeleteMaterial(id);
      showToast('Material deleted.', 'success');
      await loadMaterials();
    } catch(err) {
      showToast('Error: ' + err.message, 'danger');
    }
  }

  // ─────────────────────────────────────────────────────────────────
  // 6. TIMETABLE
  // ─────────────────────────────────────────────────────────────────
  async function loadTimetable() {
    setHtml('tp-timetable-grid', spinner('info'));
    try {
      const data = await Api.tpGetTimetable();
      const tt = data.weekly_timetable || {};
      const today = data.today || '';
      const days = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];
      const cols = days.map(day => {
        const slots = tt[day] || [];
        const isToday = day === today;
        const header = `<th class="${isToday ? 'bg-primary-subtle text-primary' : ''}">${day}${isToday ? ' <span class="badge bg-primary ms-1 small">Today</span>' : ''}</th>`;
        return { day, slots, header };
      });
      const maxPeriods = Math.max(1, ...cols.map(c => c.slots.length));
      let tableRows = '';
      for (let i = 0; i < maxPeriods; i++) {
        const cells = cols.map(col => {
          const slot = col.slots[i];
          if (!slot) return '<td class="text-center text-muted small">—</td>';
          return `<td>
            <div class="tp-tt-slot ${col.day === today ? 'tp-tt-today' : ''}">
              <div class="fw-semibold small">${slot.subject_name}</div>
              <div class="text-muted" style="font-size:.75rem">${slot.class_name}</div>
              <div class="text-muted" style="font-size:.75rem"><i class="bi bi-clock me-1"></i>${slot.start_time||''} – ${slot.end_time||''}</div>
              ${slot.classroom ? `<div class="text-muted" style="font-size:.75rem"><i class="bi bi-geo-alt me-1"></i>${slot.classroom}</div>` : ''}
            </div>
          </td>`;
        }).join('');
        tableRows += `<tr><td class="text-center fw-bold small bg-light">P${i+1}</td>${cells}</tr>`;
      }
      setHtml('tp-timetable-grid', `
        <div class="table-responsive">
          <table class="table table-bordered align-middle mb-0" style="min-width:700px">
            <thead class="table-light">
              <tr><th class="text-center">Period</th>${cols.map(c => c.header).join('')}</tr>
            </thead>
            <tbody>${tableRows || '<tr><td colspan="7" class="text-center text-muted py-4">No timetable data. Contact admin to set up your schedule.</td></tr>'}</tbody>
          </table>
        </div>`);
    } catch(err) {
      setHtml('tp-timetable-grid', errorState('Failed to load timetable: ' + err.message));
    }
  }

  // ─────────────────────────────────────────────────────────────────
  // 7. CALENDAR
  // ─────────────────────────────────────────────────────────────────
  async function loadCalendar() {
    setHtml('tp-calendar-list', spinner());
    try {
      const data = await Api.tpGetCalendar();
      const items = data.calendar || [];
      if (!items.length) {
        setHtml('tp-calendar-list', emptyState('bi-calendar', 'No upcoming calendar events.'));
        return;
      }
      const typeBgMap = {
        EVENT: 'bg-primary-subtle text-primary border-primary-subtle',
        EXAM: 'bg-danger-subtle text-danger border-danger-subtle',
        ASSIGNMENT_DEADLINE: 'bg-warning-subtle text-warning border-warning-subtle',
        ONLINE_CLASS: 'bg-success-subtle text-success border-success-subtle',
      };
      const rows = items.map(item => {
        const bg = typeBgMap[item.type] || 'bg-secondary-subtle text-secondary border-secondary-subtle';
        return `
          <div class="d-flex gap-3 align-items-start p-3 mb-2 rounded-3 border ${bg}">
            <div style="min-width:80px" class="text-center">
              <div class="fw-bold">${fmtDate(item.date)}</div>
              <span class="badge bg-white bg-opacity-50 text-dark small">${item.type.replace('_', ' ')}</span>
            </div>
            <div class="flex-grow-1">
              <div class="fw-semibold">${typeIcon(item.type)}${item.title}</div>
              ${item.description ? `<div class="small mt-1">${item.description}</div>` : ''}
              ${item.subject_name ? `<div class="small text-muted"><i class="bi bi-book me-1"></i>${item.subject_name}</div>` : ''}
              ${item.class_name ? `<div class="small text-muted"><i class="bi bi-building me-1"></i>${item.class_name}</div>` : ''}
              ${item.venue ? `<div class="small text-muted"><i class="bi bi-geo-alt me-1"></i>${item.venue}</div>` : ''}
              ${item.meeting_url ? `<a href="${item.meeting_url}" target="_blank" class="btn btn-sm btn-outline-success mt-1"><i class="bi bi-box-arrow-up-right me-1"></i>Join</a>` : ''}
            </div>
          </div>`;
      }).join('');
      setHtml('tp-calendar-list', rows);
    } catch(err) {
      setHtml('tp-calendar-list', errorState('Failed to load calendar: ' + err.message));
    }
  }

  function openEventModal() {
    const modal = document.createElement('div');
    modal.className = 'modal fade';
    modal.id = 'tp-event-modal';
    modal.tabIndex = -1;
    modal.innerHTML = `
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title fw-bold"><i class="bi bi-calendar-plus me-2 text-primary"></i>Add Calendar Event</h5>
            <button class="btn-close" data-bs-dismiss="modal"></button>
          </div>
          <div class="modal-body">
            <div class="row g-3">
              <div class="col-12">
                <label class="form-label fw-semibold small">Event Title *</label>
                <input type="text" id="tp-ev-title" class="form-control" placeholder="e.g. Sports Day">
              </div>
              <div class="col-md-6">
                <label class="form-label fw-semibold small">Date *</label>
                <input type="date" id="tp-ev-date" class="form-control">
              </div>
              <div class="col-md-6">
                <label class="form-label fw-semibold small">Category</label>
                <input type="text" id="tp-ev-category" class="form-control" placeholder="e.g. Academic, Sports">
              </div>
              <div class="col-md-6">
                <label class="form-label fw-semibold small">Audience</label>
                <select id="tp-ev-audience" class="form-select">
                  <option value="ALL">All</option><option value="STUDENTS">Students</option><option value="STAFF">Staff</option>
                </select>
              </div>
              <div class="col-md-6">
                <label class="form-label fw-semibold small">Venue</label>
                <input type="text" id="tp-ev-venue" class="form-control" placeholder="e.g. Main Auditorium">
              </div>
              <div class="col-12">
                <label class="form-label fw-semibold small">Description</label>
                <textarea id="tp-ev-desc" class="form-control" rows="2"></textarea>
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
            <button class="btn btn-primary" onclick="TP.submitEventForm()"><i class="bi bi-check-lg me-1"></i>Add Event</button>
          </div>
        </div>
      </div>`;
    document.body.appendChild(modal);
    new bootstrap.Modal(modal).show();
    modal.addEventListener('hidden.bs.modal', () => modal.remove());
  }

  async function submitEventForm() {
    const data = {
      event_title: (el('tp-ev-title')||{}).value?.trim(),
      date: (el('tp-ev-date')||{}).value,
      category: (el('tp-ev-category')||{}).value?.trim() || 'General',
      audience: (el('tp-ev-audience')||{}).value || 'ALL',
      venue: (el('tp-ev-venue')||{}).value?.trim() || null,
      description: (el('tp-ev-desc')||{}).value?.trim() || null,
    };
    if (!data.event_title || !data.date) {
      showToast('Event title and date are required.', 'warning');
      return;
    }
    try {
      await Api.tpCreateEvent(data);
      showToast('Event added to calendar!', 'success');
      bootstrap.Modal.getInstance(el('tp-event-modal'))?.hide();
      await loadCalendar();
    } catch(err) {
      showToast('Error: ' + err.message, 'danger');
    }
  }

  // ─────────────────────────────────────────────────────────────────
  // 8. ANNOUNCEMENTS
  // ─────────────────────────────────────────────────────────────────
  async function loadAnnouncements() {
    setHtml('tp-announcements-list', spinner('danger'));
    try {
      const data = await Api.tpListAnnouncements();
      if (!data.length) {
        setHtml('tp-announcements-list', emptyState('bi-megaphone', 'No announcements yet.'));
        return;
      }
      const priorityBg = { NORMAL: 'bg-light border', URGENT: 'bg-warning-subtle border-warning-subtle', CRITICAL: 'bg-danger-subtle border-danger-subtle' };
      const rows = data.map(a => `
        <div class="rounded-3 p-3 mb-3 border ${priorityBg[a.priority] || 'bg-light border'}">
          <div class="d-flex justify-content-between align-items-start gap-2 mb-2">
            <div>
              <h6 class="fw-bold mb-0">${a.title}</h6>
              <div class="small text-muted mt-1">
                <i class="bi bi-person me-1"></i>${a.author_name}
                ${a.target_class_name ? ` · <i class="bi bi-building me-1"></i>${a.target_class_name}` : ` · <span class="badge bg-secondary-subtle text-secondary">${a.target_audience}</span>`}
                · ${fmtDate(a.publication_date)}
              </div>
            </div>
            <div class="d-flex gap-1 align-items-center">
              ${statusBadge(a.priority)}
              <button class="btn btn-sm btn-outline-danger ms-1" onclick="TP.deleteAnnouncement(${a.id})">
                <i class="bi bi-trash-fill"></i>
              </button>
            </div>
          </div>
          <p class="mb-0 small">${a.message || ''}</p>
          ${a.expiry_date ? `<div class="text-muted small mt-1"><i class="bi bi-calendar-x me-1"></i>Expires: ${fmtDate(a.expiry_date)}</div>` : ''}
        </div>`).join('');
      setHtml('tp-announcements-list', rows);
    } catch(err) {
      setHtml('tp-announcements-list', errorState('Failed to load announcements: ' + err.message));
    }
  }

  function openAnnouncementModal() {
    const classes = _myClasses || [];
    const classOptions = classes.map(c => `<option value="${c.id}">${c.name}</option>`).join('');
    const modal = document.createElement('div');
    modal.className = 'modal fade';
    modal.id = 'tp-ann-modal';
    modal.tabIndex = -1;
    modal.innerHTML = `
      <div class="modal-dialog modal-lg">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title fw-bold"><i class="bi bi-megaphone-fill me-2 text-danger"></i>New Announcement</h5>
            <button class="btn-close" data-bs-dismiss="modal"></button>
          </div>
          <div class="modal-body">
            <div class="row g-3">
              <div class="col-12">
                <label class="form-label fw-semibold small">Title *</label>
                <input type="text" id="tp-ann-title" class="form-control" placeholder="e.g. Internal Exam Schedule">
              </div>
              <div class="col-md-6">
                <label class="form-label fw-semibold small">Target Audience</label>
                <select id="tp-ann-audience" class="form-select">
                  <option value="ALL">All</option>
                  <option value="STUDENTS">Students</option>
                  <option value="STAFF">Staff</option>
                </select>
              </div>
              <div class="col-md-6">
                <label class="form-label fw-semibold small">Target Class (optional)</label>
                <select id="tp-ann-class" class="form-select">
                  <option value="">All classes</option>${classOptions}
                </select>
              </div>
              <div class="col-md-6">
                <label class="form-label fw-semibold small">Priority</label>
                <select id="tp-ann-priority" class="form-select">
                  <option value="NORMAL">Normal</option>
                  <option value="URGENT">Urgent</option>
                  <option value="CRITICAL">Critical</option>
                </select>
              </div>
              <div class="col-md-6">
                <label class="form-label fw-semibold small">Expiry Date</label>
                <input type="date" id="tp-ann-expiry" class="form-control">
              </div>
              <div class="col-12">
                <label class="form-label fw-semibold small">Message *</label>
                <textarea id="tp-ann-message" class="form-control" rows="4" placeholder="Write your announcement…"></textarea>
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
            <button class="btn btn-danger" onclick="TP.submitAnnouncementForm()"><i class="bi bi-megaphone me-1"></i>Publish</button>
          </div>
        </div>
      </div>`;
    document.body.appendChild(modal);
    new bootstrap.Modal(modal).show();
    modal.addEventListener('hidden.bs.modal', () => modal.remove());
  }

  async function submitAnnouncementForm() {
    const classVal = (el('tp-ann-class')||{}).value;
    const data = {
      title: (el('tp-ann-title')||{}).value?.trim(),
      message: (el('tp-ann-message')||{}).value?.trim(),
      target_audience: (el('tp-ann-audience')||{}).value || 'ALL',
      target_class_id: classVal ? parseInt(classVal) : null,
      priority: (el('tp-ann-priority')||{}).value || 'NORMAL',
      expiry_date: (el('tp-ann-expiry')||{}).value || null,
    };
    if (!data.title || !data.message) {
      showToast('Title and message are required.', 'warning');
      return;
    }
    try {
      await Api.tpCreateAnnouncement(data);
      showToast('Announcement published!', 'success');
      bootstrap.Modal.getInstance(el('tp-ann-modal'))?.hide();
      await loadAnnouncements();
      await loadDashboard();
    } catch(err) {
      showToast('Error: ' + err.message, 'danger');
    }
  }

  async function deleteAnnouncement(id) {
    if (!confirm('Delete this announcement?')) return;
    try {
      await Api.tpDeleteAnnouncement(id);
      showToast('Announcement deleted.', 'success');
      await loadAnnouncements();
    } catch(err) {
      showToast('Error: ' + err.message, 'danger');
    }
  }

  // ─────────────────────────────────────────────────────────────────
  // 9. STUDENT PERFORMANCE
  // ─────────────────────────────────────────────────────────────────
  async function loadPerformance() {
    setHtml('tp-performance-table', spinner('success'));
    try {
      const data = await Api.tpGetPerformance();
      const perf = data.performance || [];
      if (!perf.length) {
        setHtml('tp-performance-table', emptyState('bi-bar-chart-line', 'No performance data available. Assign students to classes first.'));
        return;
      }
      const rows = perf.map(p => {
        const attRate = p.attendance_rate;
        const attColor = attRate == null ? 'secondary' : attRate >= 75 ? 'success' : attRate >= 50 ? 'warning' : 'danger';
        const marksPct = p.marks_percentage;
        const marksColor = marksPct == null ? 'secondary' : marksPct >= 75 ? 'success' : marksPct >= 50 ? 'warning' : 'danger';
        return `
          <tr>
            <td class="fw-semibold small">${p.roll_number}</td>
            <td class="small">${p.full_name}</td>
            <td class="small">${p.class_name}</td>
            <td>
              <div class="d-flex align-items-center gap-2">
                <div class="progress flex-grow-1" style="height:8px">
                  <div class="progress-bar bg-${attColor}" role="progressbar" style="width:${attRate||0}%"></div>
                </div>
                <span class="badge bg-${attColor}-subtle text-${attColor} border border-${attColor}-subtle" style="min-width:55px;text-align:right">
                  ${attRate != null ? attRate + '%' : 'N/A'}
                </span>
              </div>
              <div class="text-muted" style="font-size:.72rem">${p.present_classes}/${p.total_classes} classes</div>
            </td>
            <td class="text-center small">${p.assignments_submitted}/${p.total_assignments}</td>
            <td>
              ${marksPct != null ? `
                <div class="d-flex align-items-center gap-2">
                  <div class="progress flex-grow-1" style="height:8px">
                    <div class="progress-bar bg-${marksColor}" style="width:${marksPct}%"></div>
                  </div>
                  <span class="badge bg-${marksColor}-subtle text-${marksColor} border border-${marksColor}-subtle" style="min-width:55px;text-align:right">${marksPct}%</span>
                </div>
                <div class="text-muted" style="font-size:.72rem">${p.marks_scored}/${p.max_possible}</div>` : '<span class="text-muted small">N/A</span>'}
            </td>
          </tr>`;
      }).join('');
      setHtml('tp-performance-table', `
        <div class="table-responsive">
          <table class="table table-hover align-middle mb-0">
            <thead class="table-light">
              <tr>
                <th>Roll No</th><th>Name</th><th>Class</th>
                <th>Attendance</th>
                <th class="text-center">Assignments</th>
                <th>Marks</th>
              </tr>
            </thead>
            <tbody>${rows}</tbody>
          </table>
        </div>
        <div class="px-3 py-2 text-muted small border-top">Total: ${perf.length} students</div>`);
    } catch(err) {
      setHtml('tp-performance-table', errorState('Failed to load performance: ' + err.message));
    }
  }

  // ─────────────────────────────────────────────────────────────────
  let _initPromise = null;
  async function init() {
    if (_initPromise) return _initPromise;
    _initPromise = (async () => {
      try {
        const classData = await Api.tpMyClasses().catch(() => ({ classes: [] }));
        _myClasses = classData.classes || [];
      } catch(_) {}
      await Promise.allSettled([loadDashboard(), loadMyClasses()]);
    })().finally(() => {
      _initPromise = null;
    });
    return _initPromise;
  }

  // ─────────────────────────────────────────────────────────────────
  // PUBLIC API
  // ─────────────────────────────────────────────────────────────────
  return {
    init,
    switchTab,
    loadDashboard,
    loadMyClasses,
    loadAssignments,
    loadOnlineClasses,
    loadMaterials,
    loadTimetable,
    loadCalendar,
    loadAnnouncements,
    loadPerformance,
    openAssignmentModal,
    submitAssignmentForm,
    deleteAssignment,
    viewSubmissions,
    openGradeSubmissionModal,
    submitGrade,
    openOnlineClassModal,
    submitOnlineClassForm,
    deleteOnlineClass,
    openMaterialModal,
    submitMaterialForm,
    deleteMaterial,
    openEventModal,
    submitEventForm,
    openAnnouncementModal,
    submitAnnouncementForm,
    deleteAnnouncement,
  };
})();

window.TP = TP;

// Hook into existing app.js navigation: trigger TP.init() on first visit
(function patchNavigation() {
  const _origInit = typeof initNavigation === 'function' ? initNavigation : null;

  // Watch for teacher-portal-section activation via click
  document.addEventListener('click', function(e) {
    const link = e.target.closest('.nav-link[data-target="teacher-portal-section"]');
    if (link) {
      setTimeout(() => TP.init(), 100);
    }
  });

  // Also patch redirectRoleDashboard to support teacher portal redirect
  const _origRedirect = window.redirectRoleDashboard;
  if (typeof _origRedirect === 'function') {
    window.redirectRoleDashboard = function(role) {
      // Use Teacher Portal as default for all teacher roles
      if (role === 'CLASS_TEACHER' || role === 'SUBJECT_TEACHER') {
        const link = document.querySelector('.sidebar-nav .nav-link[data-target="teacher-portal-section"]');
        if (link) {
          link.click();
          return;
        }
      }
      _origRedirect(role);
    };
  }
})();
