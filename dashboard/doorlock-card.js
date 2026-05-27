import { LitElement, html, css } from 'https://unpkg.com/lit-element@3.3.3/lit-element.js?module';

const DOOR_INFO = {
  building_1_a: [
    { name: '1号机', floor: '1层', position: '车库', ip: '192.168.16.224' },
    { name: '2号机', floor: '2层', position: '花园', ip: '192.168.16.225' },
    { name: '3号机', floor: '-1层', position: '车库', ip: '192.168.16.226' },
    { name: '4号机', floor: '-2层', position: '车库', ip: '192.168.16.227' },
    { name: '5号机', floor: '-1层', position: '电梯左侧小门左边', ip: '192.168.16.228' },
    { name: '6号机', floor: '-1层', position: '电梯右侧小门右边', ip: '192.168.16.229' },
    { name: '7号机', floor: '-2层', position: '电梯左侧小门左边', ip: '192.168.23.164' },
    { name: '8号机', floor: '1层', position: '电梯正对', ip: '192.168.23.165' },
  ],
};

const BUILDING_NAMES = {
  building_1_a: '1栋A座',
  building_1_b: '1栋B座',
  building_1_c: '1栋C座',
  building_1_d: '1栋D座',
  building_1_e: '1栋E座',
  building_2_a: '2栋A座',
  building_2_b: '2栋B座',
  building_2_c: '2栋C座',
};

class DoorlockCard extends LitElement {
  static get properties() {
    return {
      _hass: { type: Object, state: true },
      _config: { type: Object, state: true },
      _callActive: { type: Boolean, state: true },
      _displayName: { type: String, state: true },
      _targetIp: { type: String, state: true },
      _floorLabel: { type: String, state: true },
      _positionDetail: { type: String, state: true },
      _cameraUrl: { type: String, state: true },
      _showPopup: { type: Boolean, state: true },
      _cameraLoading: { type: Boolean, state: true },
      _activeDevices: { type: Array, state: true },
      _buildingId: { type: String, state: true },
    };
  }

  static get styles() {
    return css`
      :host {
        display: block;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        --doorlock-green: #34d399;
        --doorlock-red: #f87171;
        --doorlock-blue: #60a5fa;
        --doorlock-gray: #6b7280;
        --doorlock-bg: #0f172a;
        --doorlock-card-bg: rgba(30, 41, 59, 0.7);
        --doorlock-glass: rgba(255, 255, 255, 0.06);
        --doorlock-border: rgba(255, 255, 255, 0.08);
      }

      .card {
        background: var(--doorlock-card-bg);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border: 1px solid var(--doorlock-border);
        border-radius: 20px;
        overflow: hidden;
        color: #f1f5f9;
      }

      /* Header */
      .card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 18px 20px 14px;
        border-bottom: 1px solid var(--doorlock-border);
      }
      .card-title {
        display: flex;
        align-items: center;
        gap: 10px;
      }
      .card-title-icon {
        width: 36px;
        height: 36px;
        background: linear-gradient(135deg, #34d399 0%, #059669 100%);
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 18px;
      }
      .card-title-text {
        font-size: 15px;
        font-weight: 600;
        color: #f1f5f9;
      }
      .card-title-sub {
        font-size: 11px;
        color: #94a3b8;
        margin-top: 1px;
      }
      .status-badge {
        display: flex;
        align-items: center;
        gap: 6px;
        padding: 5px 12px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 500;
        background: var(--doorlock-glass);
        border: 1px solid var(--doorlock-border);
        color: #94a3b8;
      }
      .status-badge.active {
        background: rgba(248, 113, 113, 0.15);
        border-color: rgba(248, 113, 113, 0.3);
        color: #f87171;
      }
      .status-dot {
        width: 7px;
        height: 7px;
        border-radius: 50%;
        background: #6b7280;
      }
      .status-badge.active .status-dot {
        background: #f87171;
        animation: blink 1.2s ease-in-out infinite;
      }
      @keyframes blink {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.5; transform: scale(0.85); }
      }

      /* Door grid */
      .door-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 10px;
        padding: 16px;
      }
      @media (max-width: 500px) {
        .door-grid { grid-template-columns: repeat(2, 1fr); }
      }

      /* Door item (glass button) */
      .door-btn {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 14px 8px;
        background: var(--doorlock-glass);
        border: 1px solid var(--doorlock-border);
        border-radius: 14px;
        cursor: pointer;
        transition: all 0.2s ease;
        gap: 6px;
        min-height: 82px;
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
      }
      .door-btn:hover {
        background: rgba(255, 255, 255, 0.1);
        border-color: rgba(255, 255, 255, 0.15);
        transform: translateY(-1px);
      }
      .door-btn:active {
        transform: translateY(0);
        background: rgba(255, 255, 255, 0.05);
      }
      .door-btn.current-call {
        background: rgba(248, 113, 113, 0.12);
        border-color: rgba(248, 113, 113, 0.35);
      }
      .door-btn-icon {
        font-size: 22px;
        margin-bottom: 2px;
      }
      .door-btn-name {
        font-size: 12px;
        font-weight: 600;
        color: #e2e8f0;
      }
      .door-btn-floor {
        font-size: 10px;
        color: #64748b;
        text-align: center;
        line-height: 1.2;
      }
      .door-btn.offline {
        opacity: 0.4;
        cursor: not-allowed;
      }
      .door-btn.offline:hover {
        transform: none;
        background: var(--doorlock-glass);
      }

      /* Floor indicator strip */
      .door-btn-floor-strip {
        width: 100%;
        height: 3px;
        border-radius: 2px;
        margin-bottom: 4px;
      }
      .floor-1 { background: #60a5fa; }
      .floor-2 { background: #818cf8; }
      .floor-b1 { background: #fbbf24; }
      .floor-b2 { background: #f97316; }

      /* Call popup */
      .popup-overlay {
        position: fixed;
        inset: 0;
        background: rgba(0, 0, 0, 0.7);
        backdrop-filter: blur(4px);
        z-index: 9000;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 20px;
      }
      .popup {
        width: 100%;
        max-width: 400px;
        background: var(--doorlock-card-bg);
        border: 1px solid var(--doorlock-border);
        border-radius: 24px;
        overflow: hidden;
        backdrop-filter: blur(24px);
        -webkit-backdrop-filter: blur(24px);
        box-shadow: 0 24px 60px rgba(0, 0, 0, 0.5);
        animation: popupIn 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
      }
      @keyframes popupIn {
        from { opacity: 0; transform: scale(0.88); }
        to { opacity: 1; transform: scale(1); }
      }
      .popup-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 16px 20px;
        background: rgba(248, 113, 113, 0.1);
        border-bottom: 1px solid rgba(248, 113, 113, 0.2);
      }
      .popup-header-info {
        display: flex;
        align-items: center;
        gap: 10px;
      }
      .popup-calling-icon {
        width: 38px;
        height: 38px;
        background: rgba(248, 113, 113, 0.2);
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 20px;
        animation: ring 1.2s ease-in-out infinite;
      }
      @keyframes ring {
        0%, 100% { transform: rotate(0deg); }
        20% { transform: rotate(-15deg); }
        40% { transform: rotate(15deg); }
        60% { transform: rotate(-10deg); }
        80% { transform: rotate(10deg); }
      }
      .popup-header-text {}
      .popup-calling-label {
        font-size: 10px;
        color: #f87171;
        font-weight: 600;
        letter-spacing: 0.5px;
        text-transform: uppercase;
      }
      .popup-device-name {
        font-size: 15px;
        font-weight: 600;
        color: #f1f5f9;
        margin-top: 2px;
      }
      .popup-device-location {
        font-size: 11px;
        color: #64748b;
        margin-top: 1px;
      }
      .popup-close {
        width: 32px;
        height: 32px;
        border-radius: 50%;
        background: var(--doorlock-glass);
        border: 1px solid var(--doorlock-border);
        color: #94a3b8;
        font-size: 16px;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        transition: all 0.15s;
      }
      .popup-close:hover {
        background: rgba(255, 255, 255, 0.1);
        color: #f1f5f9;
      }

      /* Video area */
      .popup-video {
        width: 100%;
        aspect-ratio: 16 / 9;
        background: #000;
        position: relative;
        overflow: hidden;
      }
      .popup-video img {
        width: 100%;
        height: 100%;
        object-fit: cover;
        display: block;
      }
      .popup-video-overlay {
        position: absolute;
        inset: 0;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 8px;
        color: rgba(255, 255, 255, 0.4);
        font-size: 12px;
        background: rgba(0, 0, 0, 0.3);
      }
      .popup-video-spinner {
        width: 28px;
        height: 28px;
        border: 2px solid rgba(255, 255, 255, 0.15);
        border-top-color: rgba(255, 255, 255, 0.5);
        border-radius: 50%;
        animation: spin 0.8s linear infinite;
      }
      @keyframes spin {
        to { transform: rotate(360deg); }
      }

      /* Action buttons */
      .popup-actions {
        display: flex;
        gap: 10px;
        padding: 14px 16px 16px;
      }
      .action-btn {
        flex: 1;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 5px;
        padding: 12px 8px;
        border-radius: 14px;
        border: none;
        cursor: pointer;
        font-size: 12px;
        font-weight: 600;
        transition: all 0.15s;
        font-family: inherit;
      }
      .action-btn:active {
        transform: scale(0.97);
      }
      .action-btn-icon {
        font-size: 22px;
        line-height: 1;
      }
      .action-btn.unlock {
        background: linear-gradient(135deg, #34d399 0%, #059669 100%);
        color: #fff;
        box-shadow: 0 4px 14px rgba(52, 211, 153, 0.35);
      }
      .action-btn.unlock:hover {
        box-shadow: 0 6px 20px rgba(52, 211, 153, 0.45);
      }
      .action-btn.answer {
        background: linear-gradient(135deg, #60a5fa 0%, #2563eb 100%);
        color: #fff;
        box-shadow: 0 4px 14px rgba(96, 165, 250, 0.35);
      }
      .action-btn.answer:hover {
        box-shadow: 0 6px 20px rgba(96, 165, 250, 0.45);
      }
      .action-btn.hangup {
        background: linear-gradient(135deg, #f87171 0%, #dc2626 100%);
        color: #fff;
        box-shadow: 0 4px 14px rgba(248, 113, 113, 0.35);
      }
      .action-btn.hangup:hover {
        box-shadow: 0 6px 20px rgba(248, 113, 113, 0.45);
      }
    `;
  }

  setConfig(config) {
    this._config = config || {};
    this._buildingId = this._config.building_id || 'building_1_a';
  }

  set hass(hass) {
    this._hass = hass;
    this._loadState();
  }

  _loadState() {
    if (!this._hass) return;
    const entityId = 'binary_sensor.uppercoast_doorlock_call_active';
    const state = this._hass.states[entityId];
    if (!state) return;

    this._callActive = state.state === 'on';
    if (this._callActive) {
      this._showPopup = true;
      const a = state.attributes || {};
      this._displayName = a.display_name || '';
      this._targetIp = a.target_ip || '';
      this._floorLabel = a.floor_label || '';
      this._positionDetail = a.position_detail || '';
    }

    // Update active devices from sensor attributes
    this._activeDevices = this._activeDevices || {};
  }

  _getFloorColor(floor) {
    if (floor.includes('1层') && !floor.includes('-')) return 'floor-1';
    if (floor.includes('2层')) return 'floor-2';
    if (floor.includes('-1层')) return 'floor-b1';
    if (floor.includes('-2层')) return 'floor-b2';
    return 'floor-1';
  }

  _getDoorStatus(ip) {
    if (!ip || !this._hass) return 'offline';
    const cameraState = this._hass.states['camera.uppercoast_doorlock_camera'];
    if (!cameraState) return 'offline';
    if (this._targetIp === ip) return 'current-call';
    return 'online';
  }

  _callService(service) {
    if (!this._hass || !this._targetIp) return;
    this._hass.callService('uppercoast_doorlock', service, {
      target_ip: this._targetIp,
    });
  }

  _closePopup() {
    this._showPopup = false;
    // do not reset call state, just hide popup
  }

  _getDoors() {
    return DOOR_INFO[this._buildingId] || DOOR_INFO['building_1_a'];
  }

  render() {
    const buildingName = BUILDING_NAMES[this._buildingId] || '1栋A座';
    const doors = this._getDoors();

    return html`
      <div class="card">
        <div class="card-header">
          <div class="card-title">
            <div class="card-title-icon">🏠</div>
            <div>
              <div class="card-title-text">云海湾门禁</div>
              <div class="card-title-sub">${buildingName}</div>
            </div>
          </div>
          <div class="status-badge ${this._callActive ? 'active' : ''}">
            <div class="status-dot"></div>
            ${this._callActive ? '呼叫中' : '待机'}
          </div>
        </div>

        <div class="door-grid">
          ${doors.map((door) => {
            const status = this._getDoorStatus(door.ip);
            const isCurrentCall = status === 'current-call';
            return html`
              <div
                class="door-btn ${status === 'offline' ? 'offline' : ''} ${isCurrentCall ? 'current-call' : ''}"
                @click=${() => { if (status !== 'offline') this._monitorDoor(door.ip); }}
              >
                <div class="door-btn-floor-strip ${this._getFloorColor(door.floor)}"></div>
                <div class="door-btn-icon">${this._getDoorEmoji(door.name)}</div>
                <div class="door-btn-name">${door.name}</div>
                <div class="door-btn-floor">${door.floor}</div>
              </div>
            `;
          })}
        </div>
      </div>

      ${this._showPopup ? this._renderPopup() : ''}
    `;
  }

  _getDoorEmoji(name) {
    const emoji = { '1号机': '🚗', '2号机': '🌷', '3号机': '🚗', '4号机': '🚗', '5号机': '🚪', '6号机': '🚪', '7号机': '🚪', '8号机': '🏠' };
    return emoji[name] || '🚪';
  }

  _monitorDoor(ip) {
    // TODO: trigger monitor stream
  }

  _renderPopup() {
    return html`
      <div class="popup-overlay" @click=${(e) => { if (e.target === e.currentTarget) this._closePopup(); }}>
        <div class="popup">
          <div class="popup-header">
            <div class="popup-header-info">
              <div class="popup-calling-icon">📞</div>
              <div class="popup-header-text">
                <div class="popup-calling-label">呼入中</div>
                <div class="popup-device-name">${this._displayName}</div>
                <div class="popup-device-location">${this._floorLabel} · ${this._positionDetail}</div>
              </div>
            </div>
            <button class="popup-close" @click=${this._closePopup}>✕</button>
          </div>

          <div class="popup-video">
            <div class="popup-video-overlay">
              <div class="popup-video-spinner"></div>
              正在加载视频...
            </div>
          </div>

          <div class="popup-actions">
            <button class="action-btn unlock" @click=${() => this._callService('unlock')}>
              <span class="action-btn-icon">🔓</span>
              解锁
            </button>
            <button class="action-btn answer" @click=${() => this._callService('answer')}>
              <span class="action-btn-icon">📞</span>
              接听
            </button>
            <button class="action-btn hangup" @click=${() => this._callService('hangup')}>
              <span class="action-btn-icon">📵</span>
              挂断
            </button>
          </div>
        </div>
      </div>
    `;
  }
}

customElements.define('doorlock-card', DoorlockCard);