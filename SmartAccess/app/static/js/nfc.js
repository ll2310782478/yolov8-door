// 简单的前端逻辑，用于 NFC 卡片管理与点击触发扫描

const apiBase = '/api/hardware';

function buildHeaders(extra = {}) {
  if (window.authHeaders) return window.authHeaders(extra);
  const token = (window.getStoredToken ? window.getStoredToken() : localStorage.getItem('token'));
  return token ? { Authorization: `Bearer ${token}`, ...extra } : { ...extra };
}

async function apiFetch(url, options = {}) {
  const merged = {
    ...options,
    headers: buildHeaders(options.headers || {})
  };

  const res = await fetch(url, merged);
  if (res.status === 401) {
    showAlert('登录已过期，请重新登录', 'danger');
    setTimeout(() => { window.location.href = '/web/auth'; }, 600);
  }
  return res;
}

async function parseJsonSafe(res) {
  try { return await res.json(); }
  catch (_) { return null; }
}

function extractErrorMessage(body, fallback) {
  if (!body) return fallback;
  if (typeof body.detail === 'string') return body.detail;
  if (body.error && typeof body.error.message === 'string') return body.error.message;
  return fallback;
}

async function fetchUsers(){
  // 获取用户列表用于选择
  try{
    const res = await apiFetch('/api/users/');
    const users = await parseJsonSafe(res);
    if(!res.ok){
      showAlert(extractErrorMessage(users, '加载用户失败'), 'danger');
      return;
    }
    if(!Array.isArray(users)){
      showAlert('用户数据格式异常', 'danger');
      return;
    }
    const sel = document.getElementById('userSelect');
    sel.innerHTML = '<option value="">-- 选择用户 --</option>';
    users.forEach(u => {
      const opt = document.createElement('option');
      opt.value = u.id;
      opt.textContent = `${u.id} - ${u.username}`;
      sel.appendChild(opt);
    });
  }catch(e){ console.error('fetchUsers error', e); }
}

async function fetchDevices(){
  const res = await apiFetch(apiBase + '/devices');
  const data = await parseJsonSafe(res);
  if(!res.ok){
    showAlert(extractErrorMessage(data, '加载设备失败'), 'danger');
    return;
  }
  const scanSel = document.getElementById('scanDeviceSelect');
  const enrollSel = document.getElementById('enrollDeviceSelect');
  scanSel.innerHTML = '';
  enrollSel.innerHTML = '';
  if(!Array.isArray(data)){
    scanSel.innerHTML = '<option value="">-- 设备数据异常 --</option>';
    enrollSel.innerHTML = '<option value="">-- 设备数据异常 --</option>';
    return;
  }

  const nfcDevices = data.filter(d => {
    const type = String(d.device_type || '').toLowerCase();
    const mode = String(d.device_mode || '').toLowerCase();
    return type.includes('nfc') || mode.includes('nfc');
  });

  const onlineNfcDevices = nfcDevices.filter(d => {
    const status = String(d.connection_status || '').toLowerCase();
    return d.is_active === true && (status === 'online' || status === 'connected');
  });

  if(nfcDevices.length === 0){
    scanSel.innerHTML = '<option value="">-- 无可用设备 --</option>';
    enrollSel.innerHTML = '<option value="">-- 无可用设备 --</option>';
  } else {
    const displayDevices = onlineNfcDevices.length > 0 ? onlineNfcDevices : nfcDevices;
    const appendOptions = (sel) => {
      displayDevices.forEach(d => {
        const opt = document.createElement('option');
        opt.value = d.device_id;
        const status = d.is_active ? (d.connection_status || 'unknown') : 'inactive';
        opt.textContent = `${d.device_name || d.device_id} (${d.device_type}) [${status}]`;
        sel.appendChild(opt);
      });
    };
    appendOptions(scanSel);
    appendOptions(enrollSel);
    if (onlineNfcDevices.length === 0) {
      showAlert('当前没有在线NFC设备，命令可能无法被执行', 'danger');
    }
  }
}

async function fetchCards(){
  const res = await apiFetch(apiBase + '/nfc/cards');
  const cards = await parseJsonSafe(res);
  const tbody = document.getElementById('cardsTable');
  
  if(!res.ok){
    const msg = extractErrorMessage(cards, '加载卡片失败');
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; color:#e53e3e;">${msg}</td></tr>`;
    return;
  }
  if(!Array.isArray(cards)){
    tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; color:#e53e3e;">卡片数据格式异常</td></tr>';
    return;
  }
  
  if(cards.length === 0){
    tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; color:#718096;">暂无卡片数据</td></tr>';
    return;
  }
  
  tbody.innerHTML = '';
  for(const c of cards){
    const tr = document.createElement('tr');
    const statusBadge = c.is_active ? '<span class="status-badge status-active">启用</span>' : '<span class="status-badge status-inactive">禁用</span>';
    tr.innerHTML = `
      <td>${c.id}</td>
      <td>${c.user_id}</td>
      <td><code style="background:#f7fafc; padding:0.25rem 0.5rem; border-radius:4px;">${c.card_number}</code></td>
      <td>${c.card_name || '-'}</td>
      <td>${statusBadge}</td>
      <td>${c.permission_end_date ? new Date(c.permission_end_date).toLocaleDateString() : '永久'} / ${c.max_daily_uses || '无限'}</td>
      <td style="display:flex; gap:0.5rem;">
        <button class="btn-outline" style="padding:0.4rem 0.8rem; font-size:0.85rem;" onclick="openEditModal(${c.id})">编辑</button>
        <button class="btn-outline" style="padding:0.4rem 0.8rem; font-size:0.85rem; color:#f56565;" onclick="deleteCard(${c.id})">删除</button>
      </td>
    `;
    tbody.appendChild(tr);
  }
}

async function createCard(evt){
  evt.preventDefault();
  const user_id = document.getElementById('userSelect').value;
  if(!user_id){
    showAlert('请选择用户', 'danger');
    return;
  }
  const card_number = document.getElementById('cardNumber').value.trim();
  const card_name = document.getElementById('cardName').value.trim();
  const permissionEnd = document.getElementById('permissionEnd').value;
  const maxDaily = document.getElementById('maxDaily').value || 0;
  
  const payload = {user_id: Number(user_id), card_number: card_number, card_name: card_name, max_daily_uses: Number(maxDaily)};
  if(permissionEnd) payload.permission_end_date = new Date(permissionEnd).toISOString();
  
  const res = await apiFetch(apiBase + '/nfc/cards', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify(payload)
  });
  
  if(res.ok){
    showAlert('卡片添加成功', 'success');
    document.getElementById('createForm').reset();
    await fetchCards();
  } else {
    const err = await parseJsonSafe(res);
    showAlert('添加失败: ' + extractErrorMessage(err, '未知错误'), 'danger');
  }
}

async function deleteCard(id){
  if(!confirm('确定删除该卡片？')) return;
  const res = await apiFetch(apiBase + '/nfc/card/' + id, {method:'DELETE'});
  if(res.ok){
    showAlert('卡片已删除', 'success');
    await fetchCards();
  } else {
    const err = await parseJsonSafe(res);
    showAlert('删除失败: ' + extractErrorMessage(err, '未知错误'), 'danger');
  }
}

function showAlert(message, type='info', timeout=4000){
  const area = document.getElementById('alertArea');
  const id = 'a' + Date.now();
  const div = document.createElement('div');
  div.id = id;
  div.className = `alert alert-${type}`;
  const closeBtn = document.createElement('button');
  closeBtn.className = 'alert-close';
  closeBtn.textContent = '✕';
  closeBtn.onclick = () => div.remove();
  div.innerHTML = `<span>${message}</span>`;
  div.appendChild(closeBtn);
  area.appendChild(div);
  if(timeout>0){ setTimeout(()=>{ try{ const e=document.getElementById(id); if(e){ e.remove(); } }catch(e){} }, timeout); }
}

async function openEditModal(id){
  const res = await apiFetch(apiBase + '/nfc/card/' + id);
  if(!res.ok){ showAlert('获取卡片失败','danger'); return; }
  const card = await res.json();
  document.getElementById('editCardId').value = card.id;
  document.getElementById('editCardName').value = card.card_name || '';
  document.getElementById('editIsActive').checked = !!card.is_active;
  document.getElementById('editPermissionEnd').value = card.permission_end_date ? card.permission_end_date.split('T')[0] : '';
  document.getElementById('editMaxDaily').value = card.max_daily_uses || 0;
  document.getElementById('editTimePeriods').value = card.time_periods || '';
  // show modal
  const modal = document.getElementById('editModal');
  modal.classList.add('show');
}

document.addEventListener('click', (e)=>{
  if(e.target && e.target.id === 'saveEdit'){
    (async ()=>{
      const id = document.getElementById('editCardId').value;
      const payload = {
        card_name: document.getElementById('editCardName').value,
        is_active: document.getElementById('editIsActive').checked,
        max_daily_uses: Number(document.getElementById('editMaxDaily').value || 0),
        time_periods: document.getElementById('editTimePeriods').value || null
      };
      const permDate = document.getElementById('editPermissionEnd').value;
      if(permDate) payload.permission_end_date = new Date(permDate).toISOString();
      const r = await apiFetch(apiBase + '/nfc/card/' + id, {method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
      if(r.ok){
        showAlert('保存成功','success');
        document.getElementById('editModal').classList.remove('show');
        await fetchCards();
      } else {
        const err = await parseJsonSafe(r);
        showAlert('保存失败: ' + extractErrorMessage(err, '未知错误'),'danger');
      }
    })();
  }
});

async function triggerScan(){
  const deviceId = document.getElementById('scanDeviceSelect').value;
  if(!deviceId){
    showAlert('请先选择“点击识别设备”', 'danger');
    return;
  }
  const status = document.getElementById('scanStatus');
  status.textContent = '📡 发送命令中...';
  
  // 创建任务
  const res = await apiFetch(apiBase + '/nfc/command', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({device_id:deviceId, command:'SCAN'})
  });
  
  if(!res.ok){
    status.textContent = '❌ 命令发送失败';
    showAlert('无法创建扫描任务', 'danger');
    return;
  }
  
  const task = await res.json();
  status.textContent = `⏳ 等待设备响应... (ID: ${task.id})`;

  // 轮询任务状态
  const start = Date.now();
  const timeout = 20000; // 20s
  while(Date.now() - start < timeout){
    await new Promise(r=>setTimeout(r, 1000));
    const st = await apiFetch(apiBase + '/nfc/command/status/' + task.id);
    const body = await st.json();
    if(body.status && body.status !== 'pending' && body.status !== 'sent'){
      let display = body.result || body.status;
      // 解析 JSON 结果并美化显示
      try{
        const resObj = JSON.parse(body.result || '{}');
        if(resObj.status === 'success' && resObj.user_id){
          display = `✓ 识别成功：用户 ID ${resObj.user_id}`;
        } else if(resObj.status === 'disabled'){
          display = '✗ 卡片已被禁用';
        } else if(resObj.status === 'expired'){
          display = '✗ 卡片权限已过期';
        } else if(resObj.status){
          display = `✗ ${resObj.status}`;
        }
      }catch(e){ }
      status.textContent = '';
      showResult(display);
      return;
    }
  }
  status.textContent = '⏱️ 超时：设备未返回结果';
}

async function triggerEnroll(){
  const deviceId = document.getElementById('enrollDeviceSelect').value;
  const userId = document.getElementById('userSelect').value;
  const status = document.getElementById('scanStatus');

  if(!deviceId){
    showAlert('请先选择“录入卡片设备”', 'danger');
    return;
  }
  if(!userId){
    showAlert('请先在下方选择要绑定的用户', 'danger');
    return;
  }

  status.textContent = '📝 已下发 ENROLL，等待刷卡...';

  try {
    const createRes = await apiFetch(apiBase + '/nfc/command', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ device_id: deviceId, command: 'ENROLL' })
    });
    const created = await parseJsonSafe(createRes);
    if(!createRes.ok){
      throw new Error(extractErrorMessage(created, '下发 ENROLL 失败'));
    }

    const taskId = created && created.id;
    if(!taskId) throw new Error('任务创建成功但缺少任务ID');

    const timeoutMs = 15000;
    const start = Date.now();
    let done = null;

    while(Date.now() - start < timeoutMs){
      await new Promise(r => setTimeout(r, 1000));
      const remain = Math.ceil((timeoutMs - (Date.now() - start)) / 1000);
      status.textContent = `📝 等待刷卡... 剩余 ${Math.max(remain, 0)} 秒`;

      const stRes = await apiFetch(apiBase + '/nfc/command/status/' + taskId);
      const stBody = await parseJsonSafe(stRes);
      if(!stRes.ok){
        throw new Error(extractErrorMessage(stBody, '查询任务状态失败'));
      }
      if(stBody && stBody.result){
        done = stBody;
        break;
      }
    }

    if(!done){
      throw new Error('录入超时，请重试');
    }

    let cardUid = '';
    try {
      const parsed = JSON.parse(done.result || '{}');
      cardUid = parsed.card_uid || parsed.uid || parsed.card_number || '';
    } catch (_) {
      cardUid = '';
    }

    if(!cardUid){
      throw new Error('任务完成但未返回卡号');
    }

    const cardInput = document.getElementById('cardNumber');
    if(cardInput) cardInput.value = cardUid;

    status.textContent = `✅ 读卡成功：${cardUid}`;
    showResult(`录入成功，卡号已自动填入新增表单：${cardUid}`);
  } catch (e) {
    status.textContent = `❌ ${e.message}`;
    showAlert(e.message || '录入失败', 'danger');
  }
}

function showResult(text){
  const card = document.getElementById('resultCard');
  const txt = document.getElementById('resultText');
  txt.textContent = text;
  card.classList.add('show');
}

document.getElementById('closeResult')?.addEventListener('click', ()=>{
  document.getElementById('resultCard').classList.remove('show');
});

// 关闭 modal 时点击外部
document.getElementById('editModal')?.addEventListener('click', (e)=>{
  if(e.target.id === 'editModal'){
    e.target.classList.remove('show');
  }
});

// 绑定事件
window.addEventListener('load', async ()=>{
  document.getElementById('createForm').addEventListener('submit', createCard);
  document.getElementById('btnScan').addEventListener('click', triggerScan);
  document.getElementById('btnEnroll').addEventListener('click', triggerEnroll);
  document.getElementById('refreshDevices').addEventListener('click', fetchDevices);
  await fetchUsers();
  await fetchDevices();
  await fetchCards();
});

