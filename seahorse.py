import seahorse
from seahorse import Program, PublicKey, u64, Account, Signer, Token, TokenAccount

class Player(Account):
    balance: u64
    wager: u64
    wins: u64
    losses: u64
    total_bet: u64
    total_won: u64
    total_lost: u64

class Game(Account):
    player1: PublicKey
    player2: PublicKey
    wager: u64
    is_active: bool

class LobbyInfo:
    game_id: u64
    player1: PublicKey
    player2: PublicKey
    wager: u64

class GameGear(Program):
    def initialize(self):
        self.game_counter = 0
        self.platform_fees = 0
        self.max_lobbies = 10

    def deposit(self, ctx, player: Player, amount: u64):
        # Overflow check
        assert player.balance + amount > player.balance, "Overflow detected"
        Token.transfer(ctx, amount, ctx.accounts.player_token_account, ctx.accounts.platform_token_account)
        player.balance += amount

    def withdraw(self, ctx, player: Player, amount: u64):
        # Underflow check
        assert player.balance >= amount, "Insufficient funds"
        Token.transfer(ctx, amount, ctx.accounts.platform_token_account, ctx.accounts.player_token_account)
        player.balance -= amount

    def withdraw_fees(self, ctx, owner: Signer):
        fees = self.platform_fees
        self.platform_fees = 0
        # Overflow check not needed for zeroing a value
        Token.transfer(ctx, fees, ctx.accounts.platform_token_account, ctx.accounts.owner_token_account)

    def create_game(self, ctx, owner: Signer, player1: PublicKey, player2: PublicKey, wager: u64):
        fee = wager // 20
        total_deduction = wager + fee
        p1 = ctx.accounts.get(player1)
        p2 = ctx.accounts.get(player2)
        # Underflow checks
        assert p1.balance >= total_deduction and p2.balance >= total_deduction, "Insufficient funds for one of the players"
        
        p1.balance -= total_deduction
        p2.balance -= total_deduction
        # Overflow check for platform fees
        assert self.platform_fees + (fee * 2) > self.platform_fees, "Overflow detected"
        self.platform_fees += fee * 2

        game_id = self.game_counter
        # Overflow check for game counter
        assert game_id + 1 > game_id, "Overflow detected"
        self.game_counter += 1
        ctx.accounts.games[game_id] = Game({
            player1: player1,
            player2: player2,
            wager: wager,
            is_active: True
        })

        return game_id

    def resolve_game(self, ctx, game_id: u64, winner: PublicKey):
        game = ctx.accounts.games[game_id]
        assert game.is_active, "Game is not active"

        winner_prize = game.wager * 2
        winner_account = ctx.accounts.get(winner)
        loser = game.player1 if game.player2 == winner else game.player2
        loser_account = ctx.accounts.get(loser)

        # Overflow checks for balance, total won, wins, total lost, and losses
        assert winner_account.balance + winner_prize > winner_account.balance, "Overflow detected"
        assert winner_account.total_won + game.wager > winner_account.total_won, "Overflow detected"
        assert winner_account.wins + 1 > winner_account.wins, "Overflow detected"
        assert loser_account.total_lost + game.wager > loser_account.total_lost, "Overflow detected"
        assert loser_account.losses + 1 > loser_account.losses, "Overflow detected"

        winner_account.balance += winner_prize
        winner_account.total_won += game.wager
        winner_account.wins += 1

        loser_account.total_lost += game.wager
        loser_account.losses += 1

        game.is_active = False
        del ctx.accounts.active_players[game.player1]
        del ctx.accounts.active_players[game.player2]
        del ctx.accounts.games[game_id]

    def set_max_lobbies(self, ctx, owner: Signer, max_lobbies: u64):
        self.max_lobbies = max_lobbies

    def get_all_game_lobbies(self, ctx) -> list[LobbyInfo]:
        lobbies = []
        for game_id, game in ctx.accounts.games.items():
            if game.is_active:
                lobbies.append(LobbyInfo(
                    game_id=game_id,
                    player1=game.player1,
                    player2=game.player2,
                    wager=game.wager
                ))
        return lobbies

    def get_balance(self, ctx, player: PublicKey) -> u64:
        player_account = ctx.accounts.get(player)
        return player_account.balance

# Main function to run the program
def main():
    program = GameGear()
    seahorse.run(program)

if __name__ == "__main__":
    main()
