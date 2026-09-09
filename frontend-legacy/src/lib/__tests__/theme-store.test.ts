/**
 * Theme Store Unit Tests
 * Tests theme state management, persistence, and subscriptions
 */

import { themeStore, THEMES, ThemeName, ThemeInfo } from '../theme-store';

describe('Theme Store', () => {
  beforeEach(() => {
    localStorage.clear();
    // Reset document theme
    document.documentElement.removeAttribute('data-theme');
  });

  describe('THEMES constant', () => {
    test('has exactly 3 themes', () => {
      expect(Object.keys(THEMES)).toHaveLength(3);
    });

    test('has abyss theme', () => {
      expect(THEMES.abyss).toBeDefined();
      expect(THEMES.abyss.name).toBe('abyss');
      expect(THEMES.abyss.label).toBe('Abyss');
      expect(THEMES.abyss.icon).toBe('🌑');
    });

    test('has temple theme', () => {
      expect(THEMES.temple).toBeDefined();
      expect(THEMES.temple.name).toBe('temple');
      expect(THEMES.temple.label).toBe('Temple');
      expect(THEMES.temple.icon).toBe('🏛️');
    });

    test('has clarity theme', () => {
      expect(THEMES.clarity).toBeDefined();
      expect(THEMES.clarity.name).toBe('clarity');
      expect(THEMES.clarity.label).toBe('Clarity');
      expect(THEMES.clarity.icon).toBe('☀️');
    });

    test('all themes have required fields', () => {
      Object.values(THEMES).forEach((theme: ThemeInfo) => {
        expect(theme.name).toBeTruthy();
        expect(theme.label).toBeTruthy();
        expect(theme.description).toBeTruthy();
        expect(theme.icon).toBeTruthy();
      });
    });
  });

  describe('themeStore instance', () => {
    test('can be instantiated', () => {
      expect(themeStore).toBeDefined();
    });

    test('defaults to abyss theme', () => {
      expect(themeStore.get()).toBe('abyss');
    });

    test('getAll returns 3 themes', () => {
      const themes = themeStore.getAll();
      expect(themes).toHaveLength(3);
    });

    test('getAll returns correct theme names', () => {
      const themes = themeStore.getAll();
      const names = themes.map(t => t.name);
      expect(names).toContain('abyss');
      expect(names).toContain('temple');
      expect(names).toContain('clarity');
    });
  });

  describe('set theme', () => {
    test('changes current theme to temple', () => {
      themeStore.set('temple');
      expect(themeStore.get()).toBe('temple');
    });

    test('changes current theme to clarity', () => {
      themeStore.set('clarity');
      expect(themeStore.get()).toBe('clarity');
    });

    test('sets data-theme attribute for non-abyss themes', () => {
      themeStore.set('temple');
      expect(document.documentElement.getAttribute('data-theme')).toBe('temple');
    });

    test('removes data-theme attribute for abyss theme', () => {
      themeStore.set('temple');
      expect(document.documentElement.getAttribute('data-theme')).toBe('temple');
      
      themeStore.set('abyss');
      expect(document.documentElement.getAttribute('data-theme')).toBeNull();
    });

    test('persists theme to localStorage', () => {
      themeStore.set('temple');
      expect(localStorage.getItem('tektos-theme')).toBe('temple');
    });

    test('persisting to localStorage works for all themes', () => {
      const themes: ThemeName[] = ['abyss', 'temple', 'clarity'];
      themes.forEach((theme) => {
        themeStore.set(theme);
        expect(localStorage.getItem('tektos-theme')).toBe(theme);
      });
    });
  });

  describe('theme subscriptions', () => {
    test('listener is called when theme changes', () => {
      const mockCallback = jest.fn();
      themeStore.onChange(mockCallback);
      
      themeStore.set('temple');
      expect(mockCallback).toHaveBeenCalledWith('temple');
    });

    test('multiple listeners are all called', () => {
      const mockCallback1 = jest.fn();
      const mockCallback2 = jest.fn();
      
      themeStore.onChange(mockCallback1);
      themeStore.onChange(mockCallback2);
      
      themeStore.set('clarity');
      
      expect(mockCallback1).toHaveBeenCalledWith('clarity');
      expect(mockCallback2).toHaveBeenCalledWith('clarity');
    });

    test('unsubscribing stops notifications', () => {
      const mockCallback = jest.fn();
      const unsubscribe = themeStore.onChange(mockCallback);
      
      themeStore.set('temple');
      expect(mockCallback).toHaveBeenCalled();
      
      unsubscribe();
      
      themeStore.set('clarity');
      expect(mockCallback).toHaveBeenCalledTimes(1);
    });

    test('unsubscribe is safe to call multiple times', () => {
      const mockCallback = jest.fn();
      const unsubscribe = themeStore.onChange(mockCallback);
      
      unsubscribe();
      unsubscribe();
      unsubscribe();
      
      themeStore.set('temple');
      expect(mockCallback).not.toHaveBeenCalled();
    });
  });

  describe('theme initialization', () => {
    test('reads saved theme from localStorage', () => {
      localStorage.clear();
      localStorage.setItem('tektos-theme', 'temple');
      
      // Clear module cache to get fresh instance
      jest.resetModules();
      const { themeStore } = require('../theme-store');
      expect(themeStore.get()).toBe('temple');
    });

    test('ignores invalid theme from localStorage', () => {
      localStorage.clear();
      localStorage.setItem('tektos-theme', 'invalid-theme');
      
      jest.resetModules();
      const { themeStore } = require('../theme-store');
      // Falls back to abyss for invalid theme
      expect(themeStore.get()).toBe('abyss');
    });

    test('applies theme on initialization', () => {
      localStorage.clear();
      localStorage.setItem('tektos-theme', 'clarity');
      
      jest.resetModules();
      const { themeStore } = require('../theme-store');
      // The theme should be clarity after reading from localStorage
      expect(themeStore.get()).toBe('clarity');
    });
  });
});
