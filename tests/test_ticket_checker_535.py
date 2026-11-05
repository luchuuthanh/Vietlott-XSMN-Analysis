import unittest
from ticket_checker import classify_ticket, check_tickets, normalize_power535_ticket

class SharedLotto535CheckerTests(unittest.TestCase):
    def test_all_prize_levels_and_separate_special(self):
        draw=[1,2,3,4,5]
        self.assertEqual(classify_ticket([1,2,3,4,5,7],draw,7,"POWER535")["tier"],"JACKPOT")
        self.assertEqual(classify_ticket([1,2,3,4,8,7],draw,7,"POWER535")["tier"],"SECOND")
        self.assertEqual(classify_ticket([1,2,3,8,9,7],draw,7,"POWER535")["tier"],"FOURTH")
        self.assertEqual(classify_ticket([8,9,10,11,12,7],draw,7,"POWER535")["tier"],"ENCOURAGEMENT")
    def test_special_group_is_independent_and_can_overlap_main(self):
        self.assertEqual(normalize_power535_ticket("01 02 03 04 05 | 09"),((1,2,3,4,5),9))
        rows=check_tickets([[1,2,3,4,9,9]],[1,2,3,4,5],9,"POWER535")
        self.assertEqual(rows[0]["Mã giải"],"SECOND")
    def test_invalid_ticket(self):
        with self.assertRaises(ValueError): normalize_power535_ticket([1,2,3,4,4,9])
        with self.assertRaises(ValueError): normalize_power535_ticket([1,2,3,4,5,13])

if __name__=="__main__": unittest.main()
