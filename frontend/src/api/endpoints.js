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
}

// World endpoints
export const world = {
  getCurrentLocation: () => apiClient.get('/world'),
  move: (direction) => apiClient.post('/world/move', { direction }),
  getExits: () => apiClient.get('/world/exits'),
}

// Combat endpoints
export const combat = {
  startCombat: () => apiClient.post('/start'),
  getStatus: () => apiClient.get('/status'),
  performAction: (action, target) => apiClient.post('/move', { move: action, target }),
}

// Inventory endpoints
export const inventory = {
  useItem: (itemId) => apiClient.post('/use', { item_id: itemId }),
  dropItem: (itemId) => apiClient.post('/drop', { item_id: itemId }),
  pickupItem: (itemId) => apiClient.post('/take', { item_id: itemId }),
}

// Equipment endpoints
export const equipment = {
  equipItem: (itemId, slot) => apiClient.post('/equip', { item_id: itemId, slot }),
  unequipItem: (slot) => apiClient.post('/unequip', { slot }),
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
