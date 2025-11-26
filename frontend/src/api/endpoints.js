import apiClient from './client'

// Auth endpoints
export const auth = {
  register: (username, password) => apiClient.post('/auth/register', { username, password }),
  login: (username, password) => apiClient.post('/auth/login', { username, password }),
  logout: () => apiClient.post('/auth/logout'),
}

// Player endpoints
export const player = {
  getStatus: () => apiClient.get('/status'),
  getInventory: () => apiClient.get('/inventory'),
  getEquipment: () => apiClient.get('/equipment'),
  getStats: () => apiClient.get('/stats'),
  getSkills: () => apiClient.get('/skills'),
  learnSkill: (skillName, category) => apiClient.post('/skills/learn', { skill_name: skillName, category }),
}

// World endpoints
export const world = {
  getCurrentLocation: () => apiClient.get('/world'),
  move: (direction) => apiClient.post('/world/move', { direction }),
  getExits: () => apiClient.get('/world/exits'),
  getTile: (x, y) => apiClient.get(`/world/tile?x=${x}&y=${y}`),
  getTilesBatch: (coordinates) => apiClient.post('/world/tiles/batch', { coordinates }),
}

// Combat endpoints
export const combat = {
  startCombat: () => apiClient.post('/combat/start'),
  getStatus: () => apiClient.get('/combat/status'),
  performAction: (action, target) => apiClient.post('/combat/move', { move: action, target }),
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
  save: (saveName) => apiClient.post('/', { save_name: saveName }),
  load: (saveId) => apiClient.post(`/${saveId}/load`),
  list: () => apiClient.get('/'),
  delete: (saveId) => apiClient.delete(`/${saveId}`),
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
