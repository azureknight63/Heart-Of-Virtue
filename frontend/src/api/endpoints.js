import apiClient from './client'

// Auth endpoints
export const auth = {
  register: (username, password) => apiClient.post('/auth/register', { username, password }),
  login: (username, password) => apiClient.post('/auth/login', { username, password }),
  logout: () => apiClient.post('/auth/logout'),
}

// Player endpoints
export const player = {
  getStatus: () => apiClient.get('/player/status'),
  getInventory: () => apiClient.get('/player/inventory'),
  getEquipment: () => apiClient.get('/player/equipment'),
  getStats: () => apiClient.get('/player/stats'),
}

// World endpoints
export const world = {
  getCurrentLocation: () => apiClient.get('/world/location'),
  move: (direction) => apiClient.post('/world/move', { direction }),
  getExits: () => apiClient.get('/world/exits'),
}

// Combat endpoints
export const combat = {
  startCombat: () => apiClient.post('/combat/start'),
  endCombat: () => apiClient.post('/combat/end'),
  getStatus: () => apiClient.get('/combat/status'),
  performAction: (action, target) => apiClient.post('/combat/action', { action, target }),
}

// Inventory endpoints
export const inventory = {
  useItem: (itemId) => apiClient.post('/inventory/use', { item_id: itemId }),
  dropItem: (itemId) => apiClient.post('/inventory/drop', { item_id: itemId }),
  pickupItem: (itemId) => apiClient.post('/inventory/pickup', { item_id: itemId }),
}

// Equipment endpoints
export const equipment = {
  equipItem: (itemId, slot) => apiClient.post('/equipment/equip', { item_id: itemId, slot }),
  unequipItem: (slot) => apiClient.post('/equipment/unequip', { slot }),
}

// Save/Load endpoints
export const saves = {
  save: (saveName) => apiClient.post('/saves/save', { save_name: saveName }),
  load: (saveId) => apiClient.post('/saves/load', { save_id: saveId }),
  list: () => apiClient.get('/saves/list'),
  delete: (saveId) => apiClient.delete(`/saves/delete/${saveId}`),
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
