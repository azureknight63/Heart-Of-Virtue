import { describe, it, expect, vi, beforeEach } from 'vitest';
import * as endpoints from './endpoints';
import apiClient from './client';

vi.mock('./client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
  }
}));

describe('endpoints', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('auth', () => {
    it('calls register endpoint', () => {
      endpoints.auth.register('user', 'pass', 'user@example.com');
      expect(apiClient.post).toHaveBeenCalledWith('/auth/register', { username: 'user', password: 'pass', email: 'user@example.com' });
    });

    it('calls login endpoint', () => {
      endpoints.auth.login('user', 'pass');
      expect(apiClient.post).toHaveBeenCalledWith('/auth/login', { username: 'user', password: 'pass' });
    });

    it('calls logout endpoint', () => {
      endpoints.auth.logout();
      expect(apiClient.post).toHaveBeenCalledWith('/auth/logout');
    });
  });

  describe('player', () => {
    it('calls getStatus endpoint', () => {
      endpoints.player.getStatus();
      expect(apiClient.get).toHaveBeenCalledWith('/status');
    });

    it('calls getFullState endpoint', () => {
      endpoints.player.getFullState();
      expect(apiClient.get).toHaveBeenCalledWith('/full-state');
    });

    it('calls getStats endpoint', () => {
      endpoints.player.getStats();
      expect(apiClient.get).toHaveBeenCalledWith('/stats');
    });

    it('calls getSkills endpoint', () => {
      endpoints.player.getSkills();
      expect(apiClient.get).toHaveBeenCalledWith('/skills');
    });

    it('calls learnSkill endpoint', () => {
      endpoints.player.learnSkill('Fireball', 'Magic');
      expect(apiClient.post).toHaveBeenCalledWith('/skills/learn', { skill_name: 'Fireball', category: 'Magic' });
    });

    it('calls allocateLevelUpPoints endpoint', () => {
      endpoints.player.allocateLevelUpPoints('strength', 5);
      expect(apiClient.post).toHaveBeenCalledWith('/level-up/allocate', { attribute: 'strength', amount: 5 });
    });
  });

  describe('world', () => {
    it('calls getCurrentLocation endpoint', () => {
      endpoints.world.getCurrentLocation();
      expect(apiClient.get).toHaveBeenCalledWith('/world');
    });

    it('calls move endpoint', () => {
      endpoints.world.move('north');
      expect(apiClient.post).toHaveBeenCalledWith('/world/move', { direction: 'north' });
    });

    it('calls getTile endpoint', () => {
      endpoints.world.getTile(10, 20);
      expect(apiClient.get).toHaveBeenCalledWith('/world/tile?x=10&y=20');
    });

    it('calls getTilesBatch endpoint', () => {
      const coords = [{ x: 1, y: 1 }];
      endpoints.world.getTilesBatch(coords);
      expect(apiClient.post).toHaveBeenCalledWith('/world/tiles/batch', { coordinates: coords });
    });

    it('calls interact endpoint', () => {
      endpoints.world.interact('npc1', 'talk', 1);
      expect(apiClient.post).toHaveBeenCalledWith('/world/interact', { target_id: 'npc1', action: 'talk', quantity: 1 });
    });

    it('calls getEvents endpoint', () => {
      endpoints.world.getEvents();
      expect(apiClient.post).toHaveBeenCalledWith('/world/events');
    });

    it('calls getCommands endpoint', () => {
      endpoints.world.getCommands();
      expect(apiClient.get).toHaveBeenCalledWith('/world/commands');
    });

    it('calls search endpoint', () => {
      endpoints.world.search();
      expect(apiClient.post).toHaveBeenCalledWith('/world/search');
    });

    it('calls getPendingEvents endpoint', () => {
      endpoints.world.getPendingEvents();
      expect(apiClient.get).toHaveBeenCalledWith('/world/events/pending');
    });

    it('calls getExploredTiles endpoint', () => {
      endpoints.world.getExploredTiles();
      expect(apiClient.get).toHaveBeenCalledWith('/world/explored');
    });
  });

  describe('combat', () => {
    it('calls startCombat endpoint', () => {
      endpoints.combat.startCombat();
      expect(apiClient.post).toHaveBeenCalledWith('/combat/start');
    });

    it('calls getStatus endpoint', () => {
      endpoints.combat.getStatus();
      expect(apiClient.get).toHaveBeenCalledWith('/combat/status');
    });

    it('calls performAction with move type', () => {
      endpoints.combat.performAction('move', { move_id: 'attack1', target_id: 'enemy1' });
      expect(apiClient.post).toHaveBeenCalledWith('/combat/move', {
        move_type: 'move',
        move_id: 'attack1',
        target_id: 'enemy1'
      });
    });

    it('calls performAction with target type', () => {
      endpoints.combat.performAction('target', { target_id: 'enemy2' });
      expect(apiClient.post).toHaveBeenCalledWith('/combat/move', {
        move_type: 'target',
        target_id: 'enemy2'
      });
    });

    it('calls performAction with direction type', () => {
      endpoints.combat.performAction('direction', { direction: 'up' });
      expect(apiClient.post).toHaveBeenCalledWith('/combat/move', {
        move_type: 'direction',
        direction: 'up'
      });
    });

    it('calls performAction with number type', () => {
      endpoints.combat.performAction('number', { value: 5 });
      expect(apiClient.post).toHaveBeenCalledWith('/combat/move', {
        move_type: 'number',
        target_id: '5'
      });
    });

    it('calls performAction with cancel type', () => {
      endpoints.combat.performAction('cancel', {});
      expect(apiClient.post).toHaveBeenCalledWith('/combat/move', {
        move_type: 'cancel'
      });
    });

    it('calls performAction with select_move_and_target type', () => {
      endpoints.combat.performAction('select_move_and_target', { move_name: 'Slash', target_id: 'goblin1' });
      expect(apiClient.post).toHaveBeenCalledWith('/combat/move', {
        move_type: 'select_move_and_target',
        move_id: 'Slash',
        target_id: 'goblin1'
      });
    });

    it('calls performAction with flee type', () => {
      endpoints.combat.performAction('flee', {});
      expect(apiClient.post).toHaveBeenCalledWith('/combat/move', {
        move_type: 'flee'
      });
    });

    it('calls collectLoot endpoint', () => {
      endpoints.combat.collectLoot(['Gold Coin', 'Potion']);
      expect(apiClient.post).toHaveBeenCalledWith('/combat/collect-loot', { item_names: ['Gold Coin', 'Potion'] });
    });

    it('calls pauseSuggestions endpoint', () => {
      endpoints.combat.pauseSuggestions(true);
      expect(apiClient.post).toHaveBeenCalledWith('/combat/suggestions/pause', { paused: true });
    });
  });

  describe('inventory', () => {
    it('calls useItem endpoint', () => {
      endpoints.inventory.useItem('item123');
      expect(apiClient.post).toHaveBeenCalledWith('/inventory/use', { item_id: 'item123' });
    });

  });

  describe('equipment', () => {
    it('calls equipItem endpoint', () => {
      endpoints.equipment.equipItem('sword1', 'main_hand');
      expect(apiClient.post).toHaveBeenCalledWith('/inventory/equip', { item_id: 'sword1', slot: 'main_hand' });
    });
  });

  describe('saves', () => {
    it('calls save endpoint', () => {
      endpoints.saves.save('mysave');
      expect(apiClient.post).toHaveBeenCalledWith('/saves', { name: 'mysave', is_autosave: false });
    });

    it('calls load endpoint', () => {
      endpoints.saves.load('save123');
      expect(apiClient.post).toHaveBeenCalledWith('/saves/save123/load');
    });

    it('calls list endpoint', () => {
      endpoints.saves.list();
      expect(apiClient.get).toHaveBeenCalledWith('/saves');
    });

    it('calls delete endpoint', () => {
      endpoints.saves.delete('save1');
      expect(apiClient.delete).toHaveBeenCalledWith('/saves/save1');
    });

    it('calls newGame endpoint', () => {
      endpoints.saves.newGame();
      expect(apiClient.post).toHaveBeenCalledWith('/game/new');
    });
  });

  describe('feedback', () => {
    it('calls submitIssue endpoint with default anonymous', () => {
      endpoints.feedback.submitIssue('bug', 'Crash on login', { steps: 'Log in' });
      expect(apiClient.post).toHaveBeenCalledWith('/feedback/issue', {
        type: 'bug',
        title: 'Crash on login',
        fields: { steps: 'Log in' },
        anonymous: false,
      });
    });

    it('calls submitIssue endpoint with anonymous=true', () => {
      endpoints.feedback.submitIssue('general', 'Great game', { message: 'Loved it' }, true);
      expect(apiClient.post).toHaveBeenCalledWith('/feedback/issue', {
        type: 'general',
        title: 'Great game',
        fields: { message: 'Loved it' },
        anonymous: true,
      });
    });
  });

  describe('shop', () => {
    it('calls getState endpoint', () => {
      endpoints.shop.getState('merchant1');
      expect(apiClient.get).toHaveBeenCalledWith('/shop/state', { params: { npc_id: 'merchant1' } });
    });

    it('calls buy endpoint', () => {
      endpoints.shop.buy('merchant1', 'item1', 2);
      expect(apiClient.post).toHaveBeenCalledWith('/shop/buy', { npc_id: 'merchant1', item_id: 'item1', quantity: 2 });
    });

    it('calls sell endpoint', () => {
      endpoints.shop.sell('merchant1', 'item1', 3);
      expect(apiClient.post).toHaveBeenCalledWith('/shop/sell', { npc_id: 'merchant1', item_id: 'item1', quantity: 3 });
    });

    it('calls buyback endpoint', () => {
      endpoints.shop.buyback('merchant1', 'item1');
      expect(apiClient.post).toHaveBeenCalledWith('/shop/buyback', { npc_id: 'merchant1', item_id: 'item1' });
    });
  });
});
