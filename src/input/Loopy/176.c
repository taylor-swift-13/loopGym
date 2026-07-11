// Source: data/benchmarks/accelerating_invariant_generation/dagger/bkley.c
extern int unknown_int(void);

int nondet_int();

/*@
  requires exclusive==0;
  requires nonexclusive==0;
  requires unowned==0;
  requires invalid>= 1;
*/
void loopy_176(int invalid, int unowned, int nonexclusive, int exclusive)
{

	
	
	
	

	

	

	

	

	while (unknown_int())
	{
		if (unknown_int())
		{
			if (! (invalid >= 1)) 
return;

			nonexclusive=nonexclusive+exclusive;
			exclusive=0;
			invalid=invalid-1;
			unowned=unowned+1;
		}
		else
		{
			if (unknown_int())
			{
				if (! (nonexclusive + unowned >=1)) 
return;

				invalid=invalid + unowned + nonexclusive-1;
				exclusive=exclusive+1;
				unowned=0;
				nonexclusive=0;
			}
			else
			{
				if (! (invalid >= 1)) 
return;

				unowned=0;
				nonexclusive=0;
				exclusive=1;
				invalid=invalid+unowned+exclusive+nonexclusive-1;
			}
		}
	}

	{;
//@ assert(exclusive >= 0);
}

	{;
//@ assert(unowned >= 0);
}

	{;
//@ assert(invalid + unowned + exclusive + nonexclusive >= 1);
}

}
