import apiClient from './client'

// Auth endpoints
export const auth = {
  register: (username, password, email) => apiClient.post('/auth/register', { username, password, email }),
  login: (username, password) => apiClient.post('/auth/login', { username, password }),
  logout: () => apiClient.post('/auth/logout'),
}

// Player endpoints
export const player = {
  getStatus: () => apiClient.get('/status'),
  getFullState: () => apiClient.get('/full-state'),
  getInventory: () => apiClient.get('/inventory'),
  getEquipment: () => apiClient.get('/equipment'),
  getStats: () => apiClient.get('/stats'),
  getSkills: () => apiClient.get('/skills'),
  learnSkill: (skillName, category) => apiClient.post('/skills/learn', { skill_name: skillName, category }),
  allocateLevelUpPoints: (attribute, amount) => apiClient.post('/level-up/allocate', { attribute, amount }),
}

// World endpoints
export const world = {
  getCurrentLocation: () => apiClient.get('/world'),
  move: (direction) => apiClient.post('/world/move', { direction }),
  getExits: () => apiClient.get('/world/exits'),
  getTile: (x, y) => apiClient.get(`/world/tile?x=${x}&y=${y}`),
  getTilesBatch: (coordinates) => apiClient.post('/world/tiles/batch', { coordinates }),
  interact: (targetId, action, quantity) => apiClient.post('/world/interact', { target_id: targetId, action, quantity }),
  getEvents: () => apiClient.post('/world/events'),
  getPendingEvents: () => apiClient.get('/world/events/pending'),
  getCommands: () => apiClient.get('/world/commands'),
  search: () => apiClient.post('/world/search'),
  getExploredTiles: () => apiClient.get('/world/explored'),
}

// Combat endpoints
export const combat = {
  startCombat: () => apiClient.post('/combat/start'),
  getStatus: () => apiClient.get('/combat/status'),
  performAction: (actionType, params) => {
    let payload = {}

    if (actionType === 'move') {
      payload = {
        move_type: 'move',
        move_id: params.move_id
      }
      // Only include target_id if it's defined and not 'player'
      if (params.target_id && params.target_id !== 'player') {
        payload.target_id = params.target_id
      }
    } else if (actionType === 'target') {
      payload = {
        move_type: 'target',
        target_id: params.target_id
      }
    } else if (actionType === 'direction') {
      payload = {
        move_type: 'direction',
        direction: params.direction
      }
    } else if (actionType === 'number') {
      payload = {
        move_type: 'number',
        target_id: params.value.toString()
      }
    } else if (actionType === 'select_move_and_target') {
      payload = {
        move_type: 'select_move_and_target',
        move_id: params.move_name,
        target_id: params.target_id
      }
    } else if (actionType === 'cancel') {
      payload = {
        move_type: 'cancel'
      }
    }

    return apiClient.post('/combat/move', payload)
  },
}

// Inventory endpoints
export const inventory = {
  useItem: (itemId) => apiClient.post('/inventory/use', { item_id: itemId }),
  dropItem: (itemId) => apiClient.post('/inventory/drop', { item_id: itemId }),
  pickupItem: (itemId) => apiClient.post('/inventory/take', { item_id: itemId }),
}

// Equipment endpoints
export const equipment = {
  equipItem: (itemId, slot) => apiClient.post('/inventory/equip', { item_id: itemId, slot }),
  unequipItem: (slot) => apiClient.post('/inventory/unequip', { slot }),
}

// Save/Load endpoints
export const saves = {
  save: (saveName, isAutosave = false) => apiClient.post('/saves', { name: saveName, is_autosave: isAutosave }),
  load: (saveId) => apiClient.post(`/saves/${saveId}/load`),
  list: () => apiClient.get('/saves'),
  delete: (saveId) => apiClient.delete(`/saves/${saveId}`),
  newGame: () => apiClient.post('/game/new'),
}

export default {
  auth,
  player,
  world,
  combat,
  inventory,
  equipment,
  saves,
}
