// Source: data/benchmarks/LinearArbitrary-SeaHorn/pie/hola/22.c

extern int unknown1();

void loopy_133(void)
{
  int x = 0;
  int y = 0;
  int z = 0;
  int k = 0;

  while(unknown1())
  {
     if(k%3 == 0)
       x++;
     y++;
     z++;
     k = x+y+z;
  }

  {;
//@ assert(x==y && y==z);
}
 
}
